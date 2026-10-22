"""Shen S1 初始相位与有限物距单通道模型；不实施迭代优化。"""
import math
import time
import numpy as np
import torch
import torch.nn.functional as F
from scipy.ndimage import label


def ring_charge(u, L=8, epsilon=.8):
    """S1 环带边界采用左闭右开，最外边界闭合；中心归第 1 带。"""
    if L < 1 or not isinstance(L,int) or epsilon <= 0:
        raise ValueError('非法环带参数')
    boundaries=(np.arange(1,L)/L)**epsilon
    u=np.asarray(u,dtype=np.float64)
    if not np.isfinite(u).all() or np.any(u<0):
        raise ValueError('半径必须非负且有限')
    return np.where(u<=1,np.searchsorted(boundaries,u,side='right')+1,0)


def pupil_arrays(size, pitch_um, cfg):
    """像素中心坐标，y 随行号增加；绘图 origin=lower 保持同一物理方向。"""
    if size*pitch_um < cfg['diameter_um']:
        raise ValueError('计算窗口不能小于真实孔径')
    coord=(np.arange(size)-(size-1)/2)*pitch_um
    r2=coord[:,None]**2+coord[None,:]**2
    u=np.sqrt(r2)/(cfg['diameter_um']/2)
    charge=ring_charge(u,cfg['L'],cfg['epsilon'])
    aperture=u<=1
    theta=np.arctan2(coord[:,None],coord[None,:])
    f=cfg['focal_mm']*1000
    # sqrt(f²+r²)-f 用有理化计算，避免近轴相消；等价于 S6/S7 的 theta=0。
    focus=-2*np.pi/(cfg['wavelength_nm']/1000)*r2/(np.sqrt(f*f+r2)+f)
    return dict(coord=coord,r2=r2,theta=theta,focus=focus,charge=charge,aperture=aperture)


def phase_for(group, arrays, cfg):
    focus=arrays['focus']
    if group=='A':
        return focus
    if group=='B':
        return focus+cfg['sign']*cfg['single_charge']*arrays['theta']
    if group=='C':
        return focus+cfg['sign']*arrays['charge']*arrays['theta']
    raise ValueError('仅有 A/B/C 三组')


def pupil_field(group, object_cm, arrays, pitch_um, cfg):
    """exp(-iωt) 下前向发散球面波；各物距孔径能量统一为 1。"""
    if not np.isfinite(object_cm) or object_cm<=0:
        raise ValueError('物距必须为正有限数，单位 cm')
    d=object_cm*10000.
    distance=np.sqrt(d*d+arrays['r2'])
    amplitude=(d/distance)*arrays['aperture']
    normalization=np.sqrt(np.sum(amplitude**2)*pitch_um**2)
    amplitude=amplitude/normalization
    sphere_phase=2*np.pi/(cfg['wavelength_nm']/1000)*arrays['r2']/(distance+d)
    field=amplitude*np.exp(1j*(sphere_phase+phase_for(group,arrays,cfg)))
    return torch.as_tensor(field,dtype=torch.complex128,device=cfg['device'])


@torch.no_grad()
def asm_memory_bounded(field,wavelength_nm,pitch_um,z_mm,padding):
    """与 N00 的同一精确频点 ASM 等价；频域乘法原位，避免 8192 网格多份复数临时数组。"""
    if field.ndim!=2 or field.dtype!=torch.complex128 or not torch.isfinite(field).all():
        raise ValueError('必须提供有限二维 complex128 场')
    if not np.isfinite([wavelength_nm,pitch_um,z_mm]).all() or min(wavelength_nm,pitch_um)<=0 or z_mm<0:
        raise ValueError('波长/pitch 必须为正、距离非负且有限')
    if not isinstance(padding,int) or padding<1:
        raise ValueError('填充倍率非法')
    h,w=field.shape
    hp,wp=h*padding,w*padding
    padded=F.pad(field,((wp-w)//2,wp-w-(wp-w)//2,(hp-h)//2,hp-h-(hp-h)//2))
    if z_mm==0:
        return padded,dict(evanescent_input_fraction=0.,expected_output_energy=float(padded.abs().square().sum())*pitch_um**2)
    spec=torch.fft.fft2(padded)
    del padded
    fy=torch.fft.fftfreq(hp,d=pitch_um,dtype=torch.float64,device=field.device)
    fx=torch.fft.fftfreq(wp,d=pitch_um,dtype=torch.float64,device=field.device)
    q=(1/(wavelength_nm/1000.)**2-fy[:,None]**2-fx[None,:]**2)
    negative=q<0
    spectral_total=float(spec.abs().square().sum())
    evanescent=float(spec[negative].abs().square().sum())/spectral_total
    # 先生成实数相位/衰减，再构造单份复传递函数；保留完整倏逝处理。
    phase=q.clamp_min(0).sqrt_().mul_(2*math.pi*z_mm*1000)
    attenuation=q.neg_().clamp_min_(0).sqrt_().mul_(-2*math.pi*z_mm*1000).exp_()
    del q,negative
    transfer=torch.polar(attenuation,phase)
    del attenuation,phase
    spec.mul_(transfer)
    del transfer
    expected=float(spec.abs().square().sum())/(hp*wp)*pitch_um**2
    output=torch.fft.ifft2(spec)
    del spec
    return output,dict(evanescent_input_fraction=evanescent,expected_output_energy=expected)


@torch.no_grad()
def simulate(group,object_cm,z_mm,cfg,size=None,pitch_um=None,padding=None,full_path=None):
    size=cfg['size'] if size is None else size
    pitch_um=cfg['pitch_um'] if pitch_um is None else pitch_um
    padding=cfg['padding'] if padding is None else padding
    arrays=pupil_arrays(size,pitch_um,cfg)
    field=pupil_field(group,object_cm,arrays,pitch_um,cfg)
    input_energy=float(field.abs().square().sum())*pitch_um**2
    del arrays
    torch.cuda.synchronize(); started=time.perf_counter()
    output,spectral=asm_memory_bounded(field,cfg['wavelength_nm'],pitch_um,z_mm,padding)
    del field
    intensity=output.abs().square()
    del output
    total=float(intensity.sum())*pitch_um**2
    n=int(round(cfg['roi_width_um']/pitch_um))
    if not np.isclose(n*pitch_um,cfg['roi_width_um']):
        raise ValueError('ROI 宽度必须是 pitch 整数倍')
    height,width=intensity.shape
    top,left=(height-n)//2,(width-n)//2
    patch=intensity[top:top+n,left:left+n].cpu().numpy().copy()
    energy=float(patch.sum())*pitch_um**2
    global_peak=float(intensity.max())
    roi_peak=float(patch.max())
    edge_width=max(1,int(round(16/pitch_um)))
    edge=intensity[:edge_width].sum()+intensity[-edge_width:].sum()+intensity[edge_width:-edge_width,:edge_width].sum()+intensity[edge_width:-edge_width,-edge_width:].sum()
    edge_fraction=float(edge)*pitch_um**2/total
    if full_path is not None:
        # 仅选择代表案例保存整域强度，其余保存完整 raw 能量统计及固定 ROI 原始强度。
        np.save(full_path,intensity.cpu().numpy())
    torch.cuda.synchronize()
    stats=dict(group=group,object_cm=float(object_cm),inverse_object_cm=1/object_cm,z_mm=float(z_mm),
               pitch_um=pitch_um,size=size,padding=padding,raw_grid_size=height,
               input_energy=input_energy,raw_energy=total,raw_energy_relative_change=(total-input_energy)/input_energy,
               spectral_energy_accounting_error=abs(total-spectral['expected_output_energy'])/input_energy,
               crop_energy=energy,crop_fraction=energy/total,edge_fraction=edge_fraction,
               global_peak_intensity=global_peak,roi_peak_intensity=roi_peak,
               global_peak_in_roi=bool(abs(global_peak-roi_peak)<=1e-12*global_peak),
               seconds=time.perf_counter()-started,**spectral)
    del intensity
    coords=(np.arange(n)-(n-1)/2)*pitch_um
    return patch,coords,stats


def locate_peak(image,coords):
    """仅定位，不修改图像；3×3 对数二次曲面的局部极大亚像素坐标。"""
    row,col=np.unravel_index(np.argmax(image),image.shape)
    offsets=np.zeros(2)
    fitted=False
    if 0<row<image.shape[0]-1 and 0<col<image.shape[1]-1:
        patch=np.log(np.maximum(image[row-1:row+2,col-1:col+2],np.finfo(float).tiny))
        yy,xx=np.mgrid[-1:2,-1:2]
        mat=np.column_stack([np.ones(9),xx.ravel(),yy.ravel(),xx.ravel()**2,xx.ravel()*yy.ravel(),yy.ravel()**2])
        b=np.linalg.lstsq(mat,patch.ravel(),rcond=None)[0]
        hessian=np.array([[2*b[3],b[4]],[b[4],2*b[5]]])
        if np.linalg.eigvalsh(hessian).max()<0:
            delta=-np.linalg.solve(hessian,b[1:3])
            if np.max(np.abs(delta))<=1:
                offsets=delta; fitted=True
    pitch=coords[1]-coords[0]
    return float(coords[col]+offsets[0]*pitch),float(coords[row]+offsets[1]*pitch),fitted


def analyze(image,coords,z_mm,cfg):
    """所有物距使用固定光轴中心 (0,0)，固定物理主瓣排除半径。"""
    x,y,fitted=locate_peak(image,coords)
    yy,xx=np.meshgrid(coords,coords,indexing='ij')
    radius=math.hypot(x,y)
    lobe_radius=1.22*(cfg['wavelength_nm']/1000)*z_mm*1000/cfg['diameter_um']
    core=(xx-x)**2+(yy-y)**2<=lobe_radius**2
    peak=float(image.max())
    side=float(image[~core].max())
    ratio=peak/side
    energy=float(image[core].sum()/image.sum())
    weights=image[core]
    localx=xx[core]-x; localy=yy[core]-y
    cov=np.array([[np.sum(weights*localx*localx),np.sum(weights*localx*localy)],
                  [np.sum(weights*localx*localy),np.sum(weights*localy*localy)]])/weights.sum()
    eigen=np.linalg.eigvalsh(cov)
    labels,count=label(image>=.5*peak)
    r,c=np.unravel_index(np.argmax(image),image.shape)
    mainlabel=labels[r,c]
    main_component=labels==mainlabel
    component_count=count
    outside_boundary=abs(x)>cfg['roi_width_um']/2-lobe_radius or abs(y)>cfg['roi_width_um']/2-lobe_radius
    reasons=[]
    if radius<=2*cfg['pitch_um']: reasons.append('主峰接近参考中心，方位角不适定')
    if ratio<cfg['thresholds']['main_sidelobe_ratio_min']: reasons.append('主峰/旁峰对比不足')
    if outside_boundary: reasons.append('主瓣靠近分析 ROI 边界')
    return dict(peak_x_um=x,peak_y_um=y,peak_radius_um=radius,angle_raw_deg=math.degrees(math.atan2(y,x)),
                angle_valid=not reasons,invalid_reason='；'.join(reasons),subpixel_fit=fitted,
                main_peak=peak,sidelobe_peak=side,main_sidelobe_ratio=ratio,main_sidelobe_contrast=(peak-side)/(peak+side),
                main_lobe_radius_um=lobe_radius,main_disk_energy_fraction_of_roi=energy,
                halfmax_components=component_count,main_halfmax_energy_fraction_of_roi=float(image[main_component].sum()/image.sum()),
                local_rms_minor_um=float(np.sqrt(eigen[0])),local_rms_major_um=float(np.sqrt(eigen[1])),
                fixed_center_x_um=0.,fixed_center_y_um=0.)


def unwrap_valid(records,max_step_deg=45.):
    """保留无效点；仅对连续有效段解缠，不跨越缺测强行拟合。"""
    segment=-1;previous=None;prev_unwrapped=None
    for record in records:
        record['angle_unwrapped_deg']=None;record['angle_step_deg']=None;record['segment']=None
        if not record['angle_valid']:
            previous=None;prev_unwrapped=None;continue
        raw=record['angle_raw_deg']
        if previous is None:
            segment+=1; unwrapped=raw
        else:
            step=(raw-previous+180)%360-180
            if abs(step)>max_step_deg:
                record['angle_valid']=False
                record['invalid_reason']='连续有效采样之间角度跃变超过预设上限'
                previous=None;prev_unwrapped=None;continue
            unwrapped=prev_unwrapped+step;record['angle_step_deg']=step
        record['angle_unwrapped_deg']=unwrapped;record['segment']=segment
        previous=raw;prev_unwrapped=unwrapped
