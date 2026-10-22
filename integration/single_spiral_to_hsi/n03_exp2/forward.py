"""复用EXP1纯数值接口；独立构造探测器级形状/相对通量模型。"""
import importlib.util
import json
from pathlib import Path
import numpy as np
from scipy.optimize import nnls


def import_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


ROOT=Path(__file__).resolve().parents[3]
EXP1=import_file('exp1_forward_readonly',ROOT/'integration/single_spiral_to_hsi/n03_exp1/forward.py')
SOLVERS=import_file('exp1_solvers_readonly',ROOT/'integration/single_spiral_to_hsi/n03_exp1/solvers.py')
WAVES=EXP1.WAVELENGTHS
MODELS=EXP1.MODELS


def load(root):
    kernels,weights,paths,records,indices=EXP1.load_assets(root)
    # EXP2光轴delta位于四格交点，纠正EXP1半像元落点；不改历史代码。
    delta=np.zeros((9,512,512),dtype=float);delta[:,255:257,255:257]=.25
    kernels[MODELS[0]]=delta
    sensor=json.loads(paths[-1].read_text(encoding='utf-8'))
    pitch=float(sensor['size'][0]*1000/sensor['res'][0])
    assert np.isclose(pitch,sensor['size'][1]*1000/sensor['res'][1],rtol=0,atol=1e-12)
    return kernels,weights,paths,records,indices,pitch


def detector_models(rebinned,shared_q):
    result={}
    for name,cube in rebinned.items():
        normalized=cube/cube.sum(axis=(1,2))[:,None,None]
        result[('shape_only',name)]=normalized
        result[('throughput_aware',name)]=normalized*shared_q[:,None,None]
    return result


def matrix(cube,weights):
    return EXP1.point_matrix(cube,weights)


def render(s,cube,weights):
    return EXP1.render_multiband(s,cube,weights).ravel()


class Operator:
    def __init__(self,a):
        self.a=a
        self.u,self.b,self.singular,self.rank,self.tol=SOLVERS.factorize(a)
        self.scale=self.singular[0]

    def solve(self,y):
        # SciPy 1.15.3在m<n的压缩秩亏问题上可误报零残差且违反KKT。
        # 补零观测行至L+1行严格不改变目标，也不添加任何先验或正则化。
        extra=self.a.shape[1]+1-self.rank
        b=np.pad(self.b/self.scale,((0,extra),(0,0)))
        projected=np.pad((self.u.T@y)/self.scale,(0,extra))
        estimate,residual=nnls(b,projected,maxiter=1000)
        gradient=b.T@(b@estimate-projected)
        kkt=max(float(max(0,-gradient.min())),float(np.max(abs(gradient*estimate))))
        if not np.isfinite(estimate).all() or estimate.min()<0 or kkt>1e-7:
            raise ArithmeticError(f'NNLS非负/有限/KKT失败：{kkt}')
        residual_full=float(np.linalg.norm(self.a@estimate-y)/max(np.linalg.norm(y),1e-300))
        return estimate,residual_full,kkt


def diagnostic(op):
    a,sv=op.a,op.singular
    norms=np.linalg.norm(a,axis=0);cos=(a.T@a)/norms[:,None]/norms[None,:]
    off=cos[~np.eye(len(sv),dtype=bool)]
    power=sv**2/np.sum(sv**2)
    return dict(shape=list(a.shape),rank=op.rank,rank_relative_tolerance=float(op.tol/sv[0]),
                singular_values=sv.tolist(),sigma_min_over_max=float(sv[-1]/sv[0]),
                kappa=float(sv[0]/sv[-1]) if op.rank==len(sv) else 'rank_deficient',
                nonzero_subspace_kappa=float(sv[0]/sv[op.rank-1]),
                effective_entropy_rank=float(np.exp(-np.sum(power[power>0]*np.log(power[power>0])))),
                max_column_cosine=float(off.max()),max_adjacent_column_cosine=float(np.diag(cos,1).max()),
                cosine=cos.tolist(),column_norms=norms.tolist(),gram=(a.T@a).tolist(),
                svd_reconstruction_relative=float(np.linalg.norm(a-op.u@op.b)/np.linalg.norm(a)))
