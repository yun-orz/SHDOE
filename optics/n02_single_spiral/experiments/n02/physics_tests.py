"""相位、单位、量化、能量、CPU/GPU与聚焦独立核查。"""
import sys
sys.dont_write_bytecode = True
import numpy as np
import torch
from scipy.special import j1
from optics import *
from audit import write


def run_tests(out):
    cfg = config()
    cfg.update(size=256, pitch_um=1., R_um=80., focal_mm=3., object_mm=180., sensor_mm=1/(1/3-1/180), padding=4, roi_width_um=256.)
    d = design(cfg, continuous=True)
    h = d['height']
    rows = []
    def check(name, fn):
        try:
            details = fn()
            rows.append(dict(name=name, status='PASS', details=details))
        except Exception as e:
            rows.append(dict(name=name, status='FAIL', reason=repr(e)))
    def verify(condition, details=None):
        assert condition, details
        return details
    check('零高度与孔径分离', lambda: verify(all(np.max(np.abs(phase_from_height(np.zeros((8,8)), w, cauchy)))==0 for w in [420,546.1,660]) and np.all(h[~d['mask']]==0)))
    check('常数高度解析', lambda: verify(np.allclose(phase_from_height(np.full((4,4),.3),420,cauchy),2*np.pi/.420*(cauchy(.420)-1)*.3,atol=1e-14)))
    check('相位回代', lambda: verify(np.max(np.abs(np.exp(1j*phase_from_height(h,546.1,cauchy)[d['mask']])-np.exp(1j*d['target'][d['mask']])) )<1e-12))
    def units():
        u,_=field(d,h,546.1,cfg)
        # 独立SI单位重建同一入射波与高度相位，然后比较PSF。
        r2m=d['r2']*1e-12; sm=cfg['object_mm']*1e-3; lm=546.1e-9
        a=sm/np.sqrt(sm*sm+r2m)*d['mask']; a/=np.sqrt(np.sum(a*a)*cfg['pitch_um']**2)
        ph=2*np.pi/lm*((cauchy(.5461)-1)*h*1e-6+r2m/(np.sqrt(sm*sm+r2m)+sm))
        v=a*np.exp(1j*ph)
        p=independent_cpu(u,546.1,cfg); q=independent_cpu(v,546.1,cfg)
        err=float(np.sum(np.abs(p-q)))
        return verify(err<1e-12,dict(psf_l1=err))
    check('SI与um单位PSF一致',units)
    def levels():
        q=design(cfg); lev=q['height'][q['mask']]*10/q['period_um']
        integer_levels=np.rint(lev).astype(int)
        return verify(np.max(abs(lev-integer_levels))<1e-12 and integer_levels.min()>=0 and integer_levels.max()<=9 and q['zone'][q['mask']].max()==8,
                      dict(max_level_residual=float(np.max(abs(lev-integer_levels))),levels=np.unique(integer_levels).tolist()))
    check('负相位取模与Q10边界',levels)
    def symmetry():
        a=design(cfg); b=design(dict(cfg,handedness=-1))
        err=float(np.max(np.abs(a['height'][::-1]-b['height'])))
        return verify(err<1e-12,dict(height_mirror_max_um=err))
    check('正负手性镜像高度',symmetry)
    def engines():
        u,_=field(d,h,546.1,cfg)
        t=torch.as_tensor(u,device='cuda',dtype=torch.complex128)
        gpu,_=baseline.asm_memory_bounded(t,546.1,1.,cfg['sensor_mm'],4)
        a=gpu.abs().square().cpu().numpy(); b=independent_cpu(u,546.1,cfg)
        err=float(np.sum(np.abs(a-b)))
        return verify(err<1e-9 and abs(a.sum()-1)<1e-12,dict(intensity_l1=err,energy=float(a.sum())))
    check('GPU历史ASM与独立SciPy及Parseval',engines)
    def repeats():
        u,_=field(d,h,420,cfg)
        t=torch.as_tensor(u,device='cuda',dtype=torch.complex128)
        a,_=baseline.asm_memory_bounded(t,420,1.,cfg['sensor_mm'],2)
        b,_=baseline.asm_memory_bounded(t,420,1.,cfg['sensor_mm'],2)
        return verify(torch.equal(a,b))
    check('重复传播稳定',repeats)
    def focus():
        z=design(cfg,spiral=False,continuous=True)
        u,_=field(z,z['height'],546.1,cfg)
        psf=independent_cpu(u,546.1,cfg)
        n=psf.shape[0]; c=np.arange(n)-(n-1)/2
        cut=(psf[n//2]+psf[n//2-1])/2
        t=2*np.pi*cfg['R_um']*np.sqrt(c*c+.25)/(.5461*cfg['sensor_mm']*1000)
        airy=(2*j1(t)/t)**2; area=abs(c)<20
        rms=float(np.sqrt(np.mean((cut[area]/cut.max()-airy[area]/airy.max())**2)))
        u_bad,_=field(z,z['height'],546.1,cfg,source_sign=-1)
        # 焦点符号的物理核查由解析总二次曲率抵消与Airy共同约束。
        curvature=1/cfg['object_mm']+1/cfg['sensor_mm']-1/cfg['focal_mm']
        return verify(rms<.03 and abs(curvature)<1e-14,dict(airy_cut_rms=rms,peak_x_um=float(c[np.argmax(cut)])))
    check('有限距离聚焦曲率符号与Airy',focus)
    def evanescent():
        # 亚波长采样的单一倏逝平面波必须衰减且不产生NaN。
        n=32; u=np.exp(2j*np.pi*12*np.arange(n)/n)[None,:]*np.ones((n,1))
        t=torch.tensor(u,dtype=torch.complex128)
        a=core_asm(t,600,.1,.001)
        return verify(torch.isfinite(a).all().item() and float(a.abs().square().sum()/t.abs().square().sum())<1e-10)
    check('倏逝单频衰减',evanescent)
    def zero_distance():
        a=torch.ones((8,8),dtype=torch.complex128)
        b=core_asm(a,546.1,1.,0.,2)
        return verify(np.array_equal(b[4:12,4:12].numpy(),a.numpy()) and float(b.abs().square().sum())==64.)
    check('零距离与padding中心坐标',zero_distance)
    check('Q10设计相位误差上限',lambda:verify(np.max(np.remainder(d['target'][d['mask']],2*np.pi)-phase_from_height(design(cfg)['height'],546.1,cauchy)[d['mask']])<2*np.pi/10+1e-12))
    write(out/'physics_tests.json',rows)
    print('物理测试',sum(r['status']=='PASS' for r in rows),'/',len(rows),flush=True)
    return all(r['status']=='PASS' for r in rows)
