"""并行定位诊断；任何估计器均不替换冻结评价器。"""
import numpy as np
from scipy.optimize import least_squares,minimize
from scipy.ndimage import map_coordinates


def quadratic(raw,c,width=3):
    rr,cc=np.unravel_index(raw.argmax(),raw.shape);half=width//2
    p=raw[rr-half:rr+half+1,cc-half:cc+half+1]
    yy,xx=np.mgrid[-half:half+1,-half:half+1]
    mat=np.column_stack([np.ones(p.size),xx.ravel(),yy.ravel(),xx.ravel()**2,(xx*yy).ravel(),yy.ravel()**2])
    target=np.log(np.maximum(p,np.finfo(float).tiny)).ravel()
    b=np.linalg.lstsq(mat,target,rcond=None)[0];H=np.array([[2*b[3],b[4]],[b[4],2*b[5]]])
    eig=np.linalg.eigvalsh(H);delta=-np.linalg.solve(H,b[1:3]);good=bool(max(eig)<0 and abs(delta).max()<=1.)
    dx=float(c[1]-c[0]);out=delta if good else np.zeros(2)
    return dict(locator='frozen3' if width==3 else f'unbounded_log{width}',width=width,
        x_um=float(c[cc]+dx*out[0]),y_um=float(c[rr]+dx*out[1]),fit_valid=good,
        gradient=b[1:3].tolist(),coefficients=b.tolist(),hessian=H.tolist(),hessian_eigenvalues=eig.tolist(),
        hessian_condition=float(np.linalg.cond(H)),unconstrained_offset_pixels=delta.tolist(),
        fitted_offset_pixels=out.tolist(),rmse_log=float(np.sqrt(np.mean((target-mat@b)**2))),
        stationarity_residual=float(np.linalg.norm(H@delta+b[1:3])),
        clipped_log_samples=int(np.sum(p<np.finfo(float).tiny)),pixel_row=int(rr),pixel_col=int(cc),
        pixel_x_um=float(c[cc]),pixel_y_um=float(c[rr]),
        failure_reason='HESSIAN_NOT_NEGATIVE' if max(eig)>=0 else 'OFFSET_EXCEEDS_ONE_PIXEL' if not good else '',
        local_raw_matrix=p.tolist())


def centroid(raw,c,width=7):
    rr,cc=np.unravel_index(raw.argmax(),raw.shape);h=width//2;p=raw[rr-h:rr+h+1,cc-h:cc+h+1]
    yy,xx=np.mgrid[-h:h+1,-h:h+1];weights=np.maximum(p-p.min(),0);mass=weights.sum();dx=float(c[1]-c[0])
    xp=float(np.sum(weights*xx)/mass);yp=float(np.sum(weights*yy)/mass)
    cov=np.array([[np.sum(weights*(xx-xp)**2),np.sum(weights*(xx-xp)*(yy-yp))],
                  [np.sum(weights*(xx-xp)*(yy-yp)),np.sum(weights*(yy-yp)**2)]])/mass*dx*dx
    return dict(locator=f'centroid{width}',x_um=float(c[cc]+dx*xp),y_um=float(c[rr]+dx*yp),fit_valid=True,
                background='局部最小强度扣除后截零，非峰值无偏估计',shape_covariance_um2=cov.tolist(),shape_eigenvalues_um2=np.linalg.eigvalsh(cov).tolist())


def constrained(raw,c,width=5,starts=8):
    rr,cc=np.unravel_index(raw.argmax(),raw.shape);h=width//2;p=raw[rr-h:rr+h+1,cc-h:cc+h+1]
    yy,xx=np.mgrid[-h:h+1,-h:h+1];xx=xx.ravel();yy=yy.ravel()
    target=np.log(np.maximum(p,np.finfo(float).tiny)).ravel()
    def prediction(v):
        a,b,v0,l11,l21,l22=v
        B=np.array([[np.exp(l11),0],[l21,np.exp(l22)]]);B=B@B.T
        x=xx-a;y=yy-b
        return v0-.5*(B[0,0]*x*x+2*B[0,1]*x*y+B[1,1]*y*y)
    fits=[]
    for angle in np.arange(starts)*2*np.pi/starts:
        guess=[.5*np.cos(angle),.5*np.sin(angle),float(target.max()),-1.7,0.,-1.7]
        sol=least_squares(lambda v:prediction(v)-target,guess,
            bounds=([-1,-1,target.max()-5,-8,-5,-8],[1,1,target.max()+5,3,5,3]),
            max_nfev=200,ftol=1e-11,gtol=1e-11,xtol=1e-11)
        fits.append(sol)
    best=min(fits,key=lambda a:np.sum(a.fun*a.fun));dx=float(c[1]-c[0]);coords=np.array([a.x[:2] for a in fits])
    near=[a.x[:2] for a in fits if np.sum(a.fun*a.fun)<=np.sum(best.fun*best.fun)+1e-9]
    return dict(locator=f'constrained_log{width}',x_um=float(c[cc]+dx*best.x[0]),y_um=float(c[rr]+dx*best.x[1]),
        fit_valid=bool(best.success),constrained_offset_pixels=best.x[:2].tolist(),boundary_active=bool(abs(best.x[:2]).max()>.9999),
        rmse_log=float(np.sqrt(np.mean(best.fun**2))),multistart_count=starts,
        near_optimum_spread_um=float(np.ptp(np.array(near),axis=0).max()*dx),all_initial_solution_offsets=coords.tolist(),
        constraint='中心±1pixel；Hessian=-LL^T；边界活跃不代表成功定位真实峰')


def interpolate(raw,c,order=3,starts=8):
    rr,cc=np.unravel_index(raw.argmax(),raw.shape);dx=float(c[1]-c[0])
    p=raw[rr-12:rr+13,cc-12:cc+13]
    def objective(v):return -float(map_coordinates(p,np.array([[12+v[1]],[12+v[0]]]),order=order,mode='nearest',prefilter=True)[0])/raw.max()
    sols=[]
    for angle in np.arange(starts)*2*np.pi/starts:
        sols.append(minimize(objective,[.5*np.cos(angle),.5*np.sin(angle)],method='Nelder-Mead',
            bounds=[(-1.5,1.5),(-1.5,1.5)],options=dict(xatol=1e-9,fatol=1e-12,maxiter=300)))
    best=min(sols,key=lambda s:s.fun)
    # 同一21×21像元物理方形，细分10倍采样；不缩放插值结果以强求能量一致。
    fcoord=(np.arange(210)+.5)/10-10.5
    yy,xx=np.meshgrid(fcoord+12,fcoord+12,indexing='ij')
    fine=map_coordinates(p,[yy,xx],order=order,mode='nearest',prefilter=True)
    orig_energy=float(p[2:23,2:23].sum()*dx*dx);new_energy=float(fine.sum()*(dx/10)**2)
    return dict(locator=f'interpolation_order{order}',x_um=float(c[cc]+dx*best.x[0]),y_um=float(c[rr]+dx*best.x[1]),fit_valid=bool(best.success),
        interpolated_peak_offset_pixels=best.x.tolist(),multistart_count=starts,
        near_optimum_spread_um=float(np.ptp([s.x for s in sols if s.fun<=best.fun+1e-8],axis=0).max()*dx),
        interpolation_order=order,interpolation_energy_before=orig_energy,interpolation_energy_after=new_energy,
        interpolation_energy_relative_change=new_energy/orig_energy-1,interpolated_min=float(fine.min()),
        interpolated_negative_fraction=float(np.mean(fine<0)),energy_note='局部物理窗口中点积分，含采样误差；没有重归一修补能量，插值不是独立物理传播')


def all_locators(raw,c,starts=8):
    return [quadratic(raw,c),centroid(raw,c),constrained(raw,c,5,starts),constrained(raw,c,7,starts),
            interpolate(raw,c,1,starts),interpolate(raw,c,3,starts)]


def synthetic_tests(seed=20261020):
    rng=np.random.default_rng(seed);c=np.arange(49)-24.;yy,xx=np.meshgrid(c,c,indexing='ij')
    cases=[]
    for angle in [0,30,60,90]:cases.append((f'elongated_{angle}',angle,5.,1.2,0.,False))
    cases.extend([('symmetric',0,2.5,2.5,0.,False),('asymmetric_shoulder',35,3.,1.6,.55,False),
                  ('competing_double',0,1.2,1.2,.99,False),('poisson_read_noise',25,3.5,1.5,.2,True)])
    records=[]
    for name,angle,s1,s2,weight,noise in cases:
        theta=np.deg2rad(angle);ct=np.cos(theta);st=np.sin(theta)
        def truth(x,y):
            a=ct*(x-.37)+st*(y+.28);b=-st*(x-.37)+ct*(y+.28)
            val=np.exp(-.5*((a/s1)**2+(b/s2)**2))
            if weight:
                sep=6 if name=='competing_double' else 3
                val+=weight*np.exp(-.5*(((a-sep)/s1)**2+(b/s2)**2))
            return val
        raw=truth(xx,yy)
        truth_solutions=[minimize(lambda q:-float(truth(q[0],q[1])),[x,y],method='BFGS') for x,y in [(0,0),(6,0),(-6,0),(0,6),(0,-6)]]
        truepeak=min(truth_solutions,key=lambda q:q.fun).x
        if noise:raw=np.maximum(0,rng.poisson(raw*1000)/1000+rng.normal(0,.005,raw.shape))
        results=all_locators(raw,c,starts=4)
        for r in results:
            r.update(case=name,true_peak_x_um=float(truepeak[0]),true_peak_y_um=float(truepeak[1]),
                position_error_um=float(np.hypot(r['x_um']-truepeak[0],r['y_um']-truepeak[1])),noise=noise)
        records.extend(results)
    return records
