"""仅扰动合成端；非周期零边界平移、卷积和固定RGB误差签名。"""
import numpy as np
from scipy.ndimage import shift,gaussian_filter
from sampling import overlap_matrix,gaussian_overlap_matrix,rebin


def definitions():
    specs=[]
    for axis in ['x','y']:
        for level in [-.5,-.25,-.1,.1,.25,.5]:
            specs.append(dict(id=f'shift_{axis}_{level:+g}',kind='common_shift_'+axis,level=level))
    signature=np.random.default_rng(20261024).uniform(-1,1,(9,2))
    signature/=np.max(abs(signature))
    for level in [.1,.25]:
        specs.append(dict(id=f'chromatic_{level:g}',kind='chromatic_shift',level=level,
                          signature=signature.tolist(),signature_seed=20261024))
    for level in [.1,.25,.5]:specs.append(dict(id=f'blur_{level:g}',kind='gaussian_blur',level=level))
    for level in [-.05,-.03,-.01,.01,.03,.05]:
        specs.append(dict(id=f'gain_{level:+g}',kind='rgb_gain',level=level,signature=[1.,-.5,-1.]))
    return specs


def perturb(fine,weights,spec,pitch):
    changed=fine.copy();new_weights=weights.copy()
    kind,level=spec['kind'],spec['level']
    offsets=np.zeros((9,2))
    if kind.startswith('common_shift_'):
        offsets[:,0 if kind.endswith('x') else 1]=level*pitch
    elif kind=='chromatic_shift':offsets=np.array(spec['signature'])*level*pitch
    if 'shift' in kind:
        for band,(dx,dy) in enumerate(offsets):
            # 输入像元为分片常数能量，一级平移对应相邻格重叠分配；边界外未知场按零处理。
            changed[band]=shift(fine[band],shift=(dy,dx),order=1,mode='constant',cval=0,prefilter=False)
    elif kind=='gaussian_blur':
        for band in range(9):
            changed[band]=gaussian_filter(fine[band],sigma=level*pitch,mode='constant',cval=0,truncate=5)
    elif kind=='rgb_gain':new_weights=weights*(1+level*np.array(spec['signature']))[:,None]
    return changed,new_weights,dict(offsets_um=offsets.tolist(),sigma_um=level*pitch if kind=='gaussian_blur' else 0,
                                    gains=(1+level*np.array(spec['signature'])).tolist() if kind=='rgb_gain' else [1,1,1],
                                    fine_energy_before=fine.sum(axis=(1,2)).tolist(),fine_energy_after=changed.sum(axis=(1,2)).tolist())


def detector_perturb(fine,weights,spec,pitch,fine_edges,detector_edges):
    """直接积分到detector，避免亚像元平移/模糊先落fine格再重采样的误差。"""
    kind,level=spec['kind'],spec['level'];offsets=np.zeros((9,2));new_weights=weights.copy()
    if kind.startswith('common_shift_'):offsets[:,0 if kind.endswith('x') else 1]=level*pitch
    elif kind=='chromatic_shift':offsets=np.array(spec['signature'])*level*pitch
    if kind=='rgb_gain':new_weights*= (1+level*np.array(spec['signature']))[:,None]
    coarse=[];fine_capture=[]
    if kind=='gaussian_blur':
        to_det=gaussian_overlap_matrix(fine_edges,detector_edges,level*pitch)
        to_fine=gaussian_overlap_matrix(fine_edges,fine_edges,level*pitch)
        for h in fine:
            coarse.append(rebin(h,to_det));fine_capture.append(float(rebin(h,to_fine).sum()))
    else:
        for h,(dx,dy) in zip(fine,offsets):
            wx=overlap_matrix(fine_edges+dx,detector_edges);wy=overlap_matrix(fine_edges+dy,detector_edges)
            coarse.append(rebin(h,wy,wx))
            fine_capture.append(float(rebin(h,overlap_matrix(fine_edges+dy,fine_edges),overlap_matrix(fine_edges+dx,fine_edges)).sum()))
    return np.stack(coarse),new_weights,dict(offsets_um=offsets.tolist(),
                  sigma_um=level*pitch if kind=='gaussian_blur' else 0,
                  gains=(1+level*np.array(spec['signature'])).tolist() if kind=='rgb_gain' else [1,1,1],
                  fine_energy_before=fine.sum(axis=(1,2)).tolist(),fine_energy_after=fine_capture,
                  method='continuous Gaussian double area integral' if kind=='gaussian_blur' else 'exact shifted source-cell overlap to detector')
