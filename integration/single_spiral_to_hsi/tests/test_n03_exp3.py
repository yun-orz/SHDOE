"""EXP3接口、物理坐标和数值目标回归。"""
import inspect
import hashlib
import numpy as np
from forward_adapter import f, sampling, noise, perturbations
from position_solver import joint_solve


def checks(model, reference):
    result=[]
    def check(name, value, limit):
        result.append(dict(name=name,value=float(value),limit=limit,passed=bool(value<=limit)))
    a,capture=model.matrix((0,0))
    cube=sampling.rebin_cube(model.fine,model.overlap)
    cube/=cube.sum(axis=(1,2))[:,None,None]
    expected=f.matrix(cube,model.weights)
    check('A0面积积分回归',np.linalg.norm(a-expected)/np.linalg.norm(expected),1e-14)
    check('EXP2B名义矩阵SHA一致',int(hashlib.sha256(a.tobytes()).hexdigest()!=reference['nominal_A_sha256']),0)
    check('尺寸103788x9',int(a.shape!=(103788,9)),0)
    check('RGB及波段索引',int(model.indices!=reference['sensor_indices'] or not np.array_equal(model.weights,reference['weights_RGB'])),0)
    coordinates=(model.det_edges[:-1]+model.det_edges[1:])/2
    for axis in [0,1]:
        centroids=[]
        for sign in [-1,1]:
            p=np.zeros(2);p[axis]=sign*.25
            shifted,_=model.cube(p)
            marginal=shifted[4].sum(axis=0 if axis==0 else 1)
            centroids.append(float(marginal@coordinates))
            old,_,_=perturbations.detector_perturb(model.fine,model.weights,dict(kind='common_shift_'+('x' if axis==0 else 'y'),level=sign*.25),model.pitch,model.edges,model.det_edges)
            old/=old.sum(axis=(1,2))[:,None,None]
            check(f'EXP2B轴{axis}符号{sign}一致',np.linalg.norm(shifted-old),1e-14)
        check(f'轴{axis}差分质心正方向',int(centroids[1]<=centroids[0]),0)
    s=np.arange(1,10,dtype=float);s/=s.sum();p=(.23,-.17)
    cube,_=model.cube(p);a,_=model.matrix(p)
    # 逐带、逐通道累加，与矩阵展平实现独立。
    rgb=np.zeros((3,186,186))
    for band in range(9):
        for channel in range(3):rgb[channel]+=s[band]*model.weights[channel,band]*cube[band]
    check('独立逐带RGB渲染',np.linalg.norm(a@s-rgb.ravel())/np.linalg.norm(rgb),1e-14)
    y=a@s;op=f.Operator(a);est,res,kkt=op.solve(y)
    check('直接残差目标',abs(res**2-np.linalg.norm(a@est-y)**2/np.linalg.norm(y)**2),1e-24)
    check('oracle光谱回归',np.linalg.norm(est-s),1e-12)
    check('KKT',kkt,1e-7)
    noisy,_=noise.protocol_q(y,noise.gaussian_direction(20261021,0,len(y)),40)
    check('Q40实际SNR',abs(noise.realized_snr(y,noisy)-40),1e-8)
    check('估计器无真值参数',int(list(inspect.signature(joint_solve).parameters)!=['y','model']),0)
    # 单点边界外能量必须流失，不得周期绕回。
    impulse=np.zeros((512,512));impulse[256,-1]=1
    moved=sampling.rebin(impulse,model.overlap,sampling.overlap_matrix(model.edges+model.pitch*.5,model.det_edges))
    check('非周期边界',float(moved.sum()),0)
    return result
