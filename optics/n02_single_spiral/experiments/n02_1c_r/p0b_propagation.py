"""受预算约束的ASM及非周期Fresnel积分、开放边界RS点积分。"""
import time
import numpy as np
import torch
from scipy.signal import CZT
from p0b_common import *


def fresnel_czt(u,coord,output,w,z_mm):
    """离散Fresnel积分的可分离CZT求值，不使用周期传播传递函数。"""
    dx=float(coord[1]-coord[0]);dy=float(output[1]-output[0]);q=(w/1000)*z_mm*1000
    n=len(coord);m=len(output)
    ch=CZT(n,m=m,w=np.exp(-2j*np.pi*dx*dy/q),a=np.exp(2j*np.pi*dx*output[0]/q))
    a=u*np.exp(1j*np.pi/q*(coord[:,None]**2+coord[None,:]**2))
    a=ch(a,axis=1)*np.exp(-2j*np.pi*coord[0]*output/q)[None,:]
    a=ch(a,axis=0)*np.exp(-2j*np.pi*coord[0]*output/q)[:,None]
    a*=dx*dx/(1j*q)*np.exp(1j*np.pi/q*(output[:,None]**2+output[None,:]**2))
    return a


def rs_points(u,c,points,w,z_mm):
    """RS1核直接中点求和，非周期；保留1+i/(kR)项，省略全局exp(ikz)。"""
    dx=float(c[1]-c[0]);yy,xx=np.meshgrid(c,c,indexing='ij');mask=abs(u)>0
    x=xx[mask];y=yy[mask];v=u[mask];z=z_mm*1000.;wl=w/1000.;k=2*np.pi/wl
    result=[]
    for xp,yp in points:
        r2=(xp-x)**2+(yp-y)**2;dist=np.sqrt(z*z+r2)
        path=r2/(dist+z)
        kernel=z/(1j*wl)*np.exp(1j*k*path)/(dist*dist)*(1+1j/(k*dist))
        result.append(np.sum(v*kernel)*dx*dx)
    return np.asarray(result)


def self_tests(cfg,h,d):
    rng=np.random.default_rng(20261020);rows=[]
    def check(name,test):
        try:
            val=test();rows.append(dict(name=name,status='PASS',details=val))
        except Exception as e:rows.append(dict(name=name,status='FAIL',reason=repr(e)))
    def require(ok,value=None):assert ok,value;return value
    def czt_direct():
        c=(np.arange(24)-11.5)*.8;o=(np.arange(13)-6)*.7;q=.5461*2100
        u=rng.normal(size=(24,24))+1j*rng.normal(size=(24,24))
        a=fresnel_czt(u,c,o,546.1,2.1)
        K=np.exp(-2j*np.pi*o[:,None]*c[None,:]/q)
        b=K@(u*np.exp(1j*np.pi*(c[:,None]**2+c[None,:]**2)/q))@K.T
        b*=.8**2/(1j*q)*np.exp(1j*np.pi*(o[:,None]**2+o[None,:]**2)/q)
        err=float(abs(a-b).max()/abs(b).max());return require(err<1e-11,dict(relative_field_error=err))
    check('CZT与显式双矩阵Fresnel积分',czt_direct)
    def parseval():
        c=np.arange(64)-31.5;u=rng.normal(size=(64,64))+1j*rng.normal(size=(64,64));u/=np.linalg.norm(u)
        a=fresnel_czt(u,c,c,500.,.128);e=float(np.sum(abs(a)**2));return require(abs(e-1)<1e-11,dict(full_Fourier_cell_energy=e))
    check('Fresnel积分单频胞Parseval',parseval)
    def rs_paraxial():
        c=np.arange(48)-23.5;yy,xx=np.meshgrid(c,c,indexing='ij');u=np.exp(-(xx*xx+yy*yy)/100).astype(complex)
        points=np.array([[0.,0.],[5.,1.],[-3.,4.]]);wl=.5461;z=10000.;k=2*np.pi/wl
        a=rs_points(u,c,points,546.1,10.)
        b=np.array([np.sum(u*np.exp(1j*k*((x-xx)**2+(y-yy)**2)/(2*z)))/(1j*wl*z) for x,y in points])
        err=float(abs(a-b).max()/abs(a).max());return require(err<1e-5,dict(relative_field_error=err))
    check('RS与小NAFresnel极限',rs_paraxial)
    def pupil_equivalence():
        a,_=input_field(d,h,425,cfg);b,_=old.field(d,h,425,cfg)
        err=float(abs(a-b).max());return require(err<1e-12,dict(field_max_error=err))
    check('独立实体相位回代与冻结入射场',pupil_equivalence)
    from p0b_locators import quadratic,constrained
    def locators():
        c=np.arange(41)-20;yy,xx=np.meshgrid(c,c,indexing='ij');raw=np.exp(-.5*((xx-.3)**2/9+(yy+.2)**2/4))
        a=quadratic(raw,c);b=constrained(raw,c,5,starts=4)
        err=max(np.hypot(a['x_um']-.3,a['y_um']+.2),np.hypot(b['x_um']-.3,b['y_um']+.2))
        return require(err<1e-6,dict(analytic_gaussian_position_error_um=float(err)))
    check('已知高斯峰定位解析核对',locators)
    return rows


def plan_resources(out,cfg):
    torch.cuda.empty_cache();mem=memory();plans=[]
    for pad in [2,4,5,6]:
        n=cfg['size']*pad
        # 既有8192复数128峰值约50字节/像素，加20%余量及256MiB背景。
        need=int(1.2*50*n*n+256*2**20)
        limit=min(.85*mem['gpu_free_bytes'],6.5*2**30)
        plans.append(dict(padding=pad,output_size=n,physical_width_um=n*cfg['pitch_um'],
            gpu_budget_bytes=need,allowed=need<limit and mem['ram_available_bytes']>2*2**30,
            limit_bytes=int(limit),reason='预检预算未满足时跳过，不尝试OOM后重试'))
    write(out/'resource_preflight.json',dict(time=now(),memory=mem,gpu_method='历史有界ASM，complex128，不修改传递函数',
        planned_domains=plans,cpu_reference_estimated_peak_bytes=1500*2**20,
        maximum_new_ASM_calls=12,maximum_new_wavelengths_nm=list(range(420,431))+[546.1,660],
        CPU_methods='非周期CZT Fresnel，仅局部RS点求积；不保存8192²以上整域数组，保存原始ROI、积分能量及缩略/剖面'))
    return {r['padding']:r for r in plans}


@torch.no_grad()
def acquire_asm(out,w,pad,cfg,h,d,plan):
    assert plan[pad]['allowed'],f'padding={pad}资源预算不允许'
    torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
    event(out,event='ASM_START',wavelength_nm=w,padding=pad,height_sha256=arrsha(h),resource_before=memory())
    u,power=input_field(d,h,w,cfg)
    t=torch.as_tensor(u,device='cuda',dtype=torch.complex128)
    result,spectral=old.baseline.asm_memory_bounded(t,w,cfg['pitch_um'],cfg['sensor_mm'],pad)
    intensity=result.abs().square();del result,t
    n=intensity.shape[0];half=256;mid=n//2
    raw=intensity[mid-half:mid+half,mid-half:mid+half].cpu().numpy().copy();c=np.arange(512)-255.5
    total=float(intensity.sum());b=16
    edges=float(intensity[:b].sum()+intensity[-b:].sum()+intensity[b:-b,:b].sum()+intensity[b:-b,-b:].sum())
    rec=dict(wavelength_nm=w,padding=pad,pitch_um=1.,size=2048,physical_width_um=n,
        input_energy=float(np.sum(abs(u)**2)),raw_energy=total,crop_energy=float(raw.sum()),crop_fraction=float(raw.sum()/total),
        global_peak_in_roi=bool(raw.max()>=float(intensity.max())*(1-1e-12)),edge_fraction=edges/total,boundary_share_16um=edges/total,
        boundary_energy_incident=edges,evanescent_input_fraction=spectral['evanescent_input_fraction'],
        spectral_energy_accounting_error=abs(total-spectral['expected_output_energy']),
        height_array_sha256=arrsha(h),incident_unscaled_power_um2=power,source='NEW_FIXED_HEIGHT_ASM')
    for width in [512,1024,2048,4096,8192]:
        rec[f'capture_{width}_um']=float(intensity[(n-width)//2:(n+width)//2,(n-width)//2:(n+width)//2].sum()) if width<=n else None
    rec=old.measure(raw,c,rec,cfg,w)
    thumb=intensity.reshape(n//16,16,n//16,16).mean(dim=(1,3)).cpu().numpy()
    profile=intensity[n//2].cpu().numpy();peak_vram=torch.cuda.max_memory_allocated();del intensity
    torch.cuda.synchronize();rec.update(seconds=time.perf_counter()-start,gpu_peak_allocated_bytes=peak_vram,resource_after=memory())
    path=out/'propagation'/f'ASM_pad{pad}_{w:g}nm.npz'
    npz(path,raw_roi=raw,normalized_psf=raw/raw.sum(),coords_um=c,record_json=json.dumps(clean(rec),ensure_ascii=False),
        full_domain_thumbnail_raw_mean=thumb,full_domain_y05um_profile_raw=profile,thumbnail_pixel_um=16.)
    event(out,event='ASM_COMPLETE',wavelength_nm=w,padding=pad,seconds=rec['seconds'],gpu_peak_bytes=peak_vram,
          resource=rec['resource_after'],path=path.relative_to(out),sha256=sha(path))
    print(f'ASM 固定高度 {w:g}nm pad{pad} edge={edges/total:.9f} {rec["n01_status"]} {rec["seconds"]:.2f}s',flush=True)
    return raw,c,rec


def acquire_fresnel(out,w,cfg,h,d):
    start=time.perf_counter();u,power=input_field(d,h,w,cfg);c=np.arange(512)-255.5
    a=fresnel_czt(u,d['coord'],c,w,cfg['sensor_mm']);raw=abs(a)**2
    rec=dict(wavelength_nm=w,method='OPEN_FRESNEL_CZT',source='SIMULATED_PARAXIAL',pitch_um=1.,height_array_sha256=arrsha(h),
             roi_energy_incident=float(raw.sum()),seconds=time.perf_counter()-start,resource=memory(),
             maximum_quartic_phase_error_bound_rad=float(2*np.pi/(w/1000)*(cfg['R_um']+np.sqrt(2)*256)**4/(8*(cfg['sensor_mm']*1000)**3)))
    npz(out/'propagation'/f'open_fresnel_{w:g}nm.npz',raw_roi=raw,normalized_psf=raw/raw.sum(),coords_um=c,record_json=json.dumps(clean(rec),ensure_ascii=False))
    event(out,event='OPEN_FRESNEL_COMPLETE',**rec)
    return raw,c,rec
