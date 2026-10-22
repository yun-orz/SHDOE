"""固定像元高度的分块RS面积求积和精确选点周期ASM。"""
from r2_common import *


@torch.no_grad()
def rs(source,points,w,cfg,q,device='cuda',pixel_chunk=8192,point_chunk=4,progress=None):
    """同一固定K，源像元内部只改变球面场/传播核；高度和遮光掩模分片常值。"""
    start=time.perf_counter();dtype=torch.float64
    offsets=(np.arange(q)+.5)/q-.5;oy,ox=np.meshgrid(offsets,offsets,indexing='ij')
    ox=torch.as_tensor(ox.ravel(),dtype=dtype,device=device);oy=torch.as_tensor(oy.ravel(),dtype=dtype,device=device)
    points=torch.as_tensor(np.asarray(points),dtype=dtype,device=device)
    total=torch.zeros(len(points),dtype=torch.complex128,device=device);incident=torch.zeros((),dtype=dtype,device=device)
    wl=w/1000.;k=2*np.pi/wl;z=cfg['sensor_mm']*1000;s=cfg['object_mm']*1000;n=1.5292+.008/wl**2
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    nsource=len(source['x'])
    for first in range(0,nsource,pixel_chunk):
        end=min(first+pixel_chunk,nsource)
        x=torch.as_tensor(source['x'][first:end],dtype=dtype,device=device)[:,None]+ox[None,:]
        y=torch.as_tensor(source['y'][first:end],dtype=dtype,device=device)[:,None]+oy[None,:]
        h=torch.as_tensor(source['height'][first:end],dtype=dtype,device=device)[:,None]
        r2=x*x+y*y;distin=torch.sqrt(s*s+r2);a=source['K']*s/distin
        u=a*torch.exp(1j*k*(r2/(distin+s)+(n-cfg['n_env'])*h))
        incident+=(a*a).sum()/(q*q)
        for pfirst in range(0,len(points),point_chunk):
            pp=points[pfirst:pfirst+point_chunk]
            r2=(x[None,:,:]-pp[:,0,None,None])**2+(y[None,:,:]-pp[:,1,None,None])**2
            dist=torch.sqrt(z*z+r2)
            # 省略同一exp(ikz)，以有理化光程避免大活塞相位减法。
            kernel=z/(1j*wl)*torch.exp(1j*k*r2/(dist+z))/(dist*dist)*(1+1j/(k*dist))
            total[pfirst:pfirst+len(pp)]+=(u[None,:,:]*kernel).sum(dim=(1,2))/(q*q)
        if progress and (first//pixel_chunk)%32==0:progress(first/nsource)
    if device=='cuda':torch.cuda.synchronize()
    result=total.cpu().numpy();inc=float(incident)
    return result,dict(seconds=time.perf_counter()-start,incident_quadrature_energy=inc,
        fixed_K=source['K'],source_pixels=nsource,input_subdivision=q,pixel_chunk=pixel_chunk,point_chunk=point_chunk,
        gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device=='cuda' else None,resource=memory())


@torch.no_grad()
def periodic_points(u,points,w,cfg,pad,device='cuda',row_chunk=128):
    """只保留FFT频谱，逐行块传递后选点逆DFT；不构造整域强度或完整传递函数。"""
    start=time.perf_counter();torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
    n=u.shape[0]*pad;h=u.shape[0];left=(n-h)//2
    a=torch.zeros((n,n),dtype=torch.complex128,device=device)
    a[left:left+h,left:left+h]=torch.as_tensor(u,device=device)
    spec=torch.fft.fft2(a);del a
    f=torch.fft.fftfreq(n,d=1.,dtype=torch.float64,device=device)
    p=torch.tensor(points,dtype=torch.float64,device=device)
    # 数组索引中心(N-1)/2含半像素。外部点按周期延拓计算并单独标记。
    xp=p[:,0]+(n-1)/2;yp=p[:,1]+(n-1)/2
    ex=torch.exp(2j*np.pi*f[:,None]*xp[None,:])
    output=torch.zeros(len(points),dtype=torch.complex128,device=device)
    spectral_energy=torch.zeros((),dtype=torch.float64,device=device)
    wl=w/1000.;z=cfg['sensor_mm']*1000
    for first in range(0,n,row_chunk):
        fy=f[first:first+row_chunk];f2=fy[:,None]**2+f[None,:]**2
        root=torch.sqrt(1/wl**2-f2)
        # 传递核减去全局活塞的有理式，与精确ASM相同，不做频率滤波。
        transfer=torch.exp(-2j*np.pi*z*f2/(root+1/wl))
        block=spec[first:first+len(fy)]*transfer
        spectral_energy+=(block.abs()**2).sum()
        row_values=block@ex
        output+=(row_values*torch.exp(2j*np.pi*fy[:,None]*yp[None,:])).sum(dim=0)/(n*n)
    result=output.cpu().numpy();total=float(spectral_energy)/(n*n);del spec,ex
    torch.cuda.synchronize()
    return result,dict(seconds=time.perf_counter()-start,finite_periodic_energy=total,N=n,padding=pad,
        row_chunk=row_chunk,gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),resource=memory(),
        implementation='FFT谱+分块精确ASM相位+选点逆DFT；无整域输出强度，无滤波，无吸收边界')


def self_tests(cfg,source):
    tests=[]
    def check(name,fn):
        try:tests.append(dict(name=name,status='PASS',details=fn()))
        except Exception as e:tests.append(dict(name=name,status='FAIL',reason=repr(e)))
    def verify(ok,detail):assert ok,detail;return detail
    def rs_analytic():
        # 小方形孔径远近轴轴上积分趋于面积/(lambda*z)，包含输入场与RS法向因子。
        sx,sy=np.meshgrid(np.arange(8)-3.5,np.arange(8)-3.5,indexing='xy')
        src=dict(x=sx.ravel(),y=sy.ravel(),height=np.zeros(64),K=1.,pixel_area_um2=1.)
        conf=dict(cfg,object_mm=1e8,sensor_mm=1e5)
        a,_=rs(src,[[0.,0.]],500,conf,4,device='cpu',pixel_chunk=7,point_chunk=1)
        target=64/(1j*.5*1e8)
        err=float(abs(a[0]-target)/abs(target));return verify(err<1e-5,dict(relative_field_error=err))
    check('RS轴上小方孔远场解析幅值与面积',rs_analytic)
    def rs_symmetry():
        xx,yy=np.meshgrid(np.arange(8)-3.5,np.arange(8)-3.5)
        src=dict(x=xx.ravel(),y=yy.ravel(),height=np.zeros(64),K=1/8,pixel_area_um2=1.)
        a,_=rs(src,[[20.,3.],[-20.,-3.]],546.1,cfg,4,device='cpu',pixel_chunk=9,point_chunk=2)
        err=float(abs(a[0]-a[1])/abs(a[0]));return verify(err<1e-12,dict(centrosymmetric_aperture_complex_error=err))
    check('对称控制孔径RS对边复场对称',rs_symmetry)
    def chunk_and_device():
        src={k:(v[:101] if isinstance(v,np.ndarray) else v) for k,v in source.items()}
        points=np.array([[.5,.5],[2047.5,.5]])
        a,_=rs(src,points,420,cfg,2,'cpu',17,1)
        b,_=rs(src,points,420,cfg,2,'cuda',31,2)
        err=float(abs(a-b).max()/abs(a).max());return verify(err<1e-10,dict(cpu_gpu_and_chunk_relative_field_error=err))
    check('RS分块划分与CPU_GPU独立内核一致',chunk_and_device)
    def direct_midpoint():
        # 独立NumPy展开子像元，不使用主求解器的广播/分块路径。
        src={k:(v[:23] if isinstance(v,np.ndarray) else v) for k,v in source.items()}
        p=np.array([[1.,-2.],[2015.5,.5]]);q=4;v=[]
        wl=.42;k=2*np.pi/wl;s=cfg['object_mm']*1000;z=cfg['sensor_mm']*1000;dn=1.5292+.008/wl**2-1
        for xp,yp in p:
            value=0j
            for x,y,h in zip(src['x'],src['y'],src['height']):
                for i in range(q):
                    for j in range(q):
                        xs=x+(i+.5)/q-.5;ys=y+(j+.5)/q-.5;rin=np.sqrt(s*s+xs*xs+ys*ys)
                        d2=(xs-xp)**2+(ys-yp)**2;R=np.sqrt(z*z+d2)
                        value+=src['K']*s/rin*np.exp(1j*k*((xs*xs+ys*ys)/(rin+s)+dn*h))*z/(1j*wl)*np.exp(1j*k*d2/(R+z))/R**2*(1+1j/(k*R))/(q*q)
            v.append(value)
        a,_=rs(src,p,420,cfg,4,'cpu',11,1)
        err=float(abs(a-v).max()/abs(a).max());return verify(err<1e-11,dict(independent_loop_field_error=err))
    check('固定高度子像元RS与独立显式循环',direct_midpoint)
    def point_asm():
        rng=np.random.default_rng(20261020);u=rng.normal(size=(32,32))+1j*rng.normal(size=(32,32));u/=np.linalg.norm(u)
        conf=dict(cfg,sensor_mm=.003);p=np.array([[-3.5,4.5],[.5,.5],[8.5,-7.5]])
        a,_=periodic_points(u,p,546.1,conf,2)
        n=64;pad=np.zeros((n,n),complex);pad[16:48,16:48]=u;f=np.fft.fftfreq(n);f2=f[:,None]**2+f[None,:]**2
        phase=np.exp(-2j*np.pi*3*f2/(np.sqrt(1/.5461**2-f2)+1/.5461))
        full=np.fft.ifft2(np.fft.fft2(pad)*phase)
        b=np.array([full[int(round(y+31.5)),int(round(x+31.5))] for x,y in p]);err=float(abs(a-b).max())
        return verify(err<1e-12,dict(point_inverse_DFT_max_complex_error=err))
    check('选点ASM逆DFT与独立完整IFFT',point_asm)
    return tests
