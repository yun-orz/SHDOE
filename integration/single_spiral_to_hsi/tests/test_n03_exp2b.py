"""EXP2B的位置网格、固定名义矩阵、零回归及B固定点工程检查。"""
import numpy as np


def a_checks(positions,nominal,independent_render,cube,weights):
    checks=[]
    def ck(name,passed,value=None):checks.append(dict(name=name,passed=bool(passed),value=value))
    ck('17个唯一位置且零位只出现一次',len(positions)==17 and len(set((p['dx_pixel'],p['dy_pixel']) for p in positions))==17 and sum(p['axis']=='origin' for p in positions)==1)
    for axis in ['x','y']:
        selected=[p['signed_pixel'] for p in positions if p['axis']==axis]
        ck(axis+'正负位移完整',sorted(selected)==[-.05,-.02,-.01,-.005,.005,.01,.02,.05])
    rng=np.random.default_rng(20261021);s=rng.random(9);s/=s.sum()
    rendered=independent_render(s,cube,weights)
    relative=float(np.linalg.norm(rendered-nominal.a@s)/np.linalg.norm(rendered))
    ck('独立逐带渲染',relative<1e-10,relative)
    v=rng.normal(size=len(rendered));lhs=float((nominal.a@s)@v);rhs=float(s@(nominal.a.T@v))
    adj=abs(lhs-rhs)/max(1,abs(lhs),abs(rhs));ck('固定名义伴随',adj<1e-10,adj)
    estimate,residual,kkt=nominal.solve(rendered)
    ck('名义NNLS非负KKT',estimate.min()>=0 and kkt<1e-7,kkt)
    return checks


def b_checks(points,old_points,old_ids,source,cfg):
    checks=[]
    def ck(name,passed,value=None):checks.append(dict(name=name,passed=bool(passed),value=value))
    ck('原预注册8点ID顺序',len(points)==8 and [p['point_id'] for p in points]==list(old_ids))
    xy=np.array([[p['x_um'],p['y_um']] for p in points])
    ck('历史q8点坐标逐位相等',np.array_equal(xy,old_points),xy.tolist())
    ck('全部原边界像元中心',all(p['q8_preregistered'] and p['in_16um_boundary_strip'] for p in points))
    ck('源像元数量与K',len(source['x'])==785456 and abs(source['K']-.0011283397992865316)<1e-16)
    ck('固定几何',cfg['pitch_um']==1 and cfg['padding']==2 and cfg['sensor_mm']==22.495 and cfg['object_mm']==180 and cfg['R_um']==500)
    return checks
