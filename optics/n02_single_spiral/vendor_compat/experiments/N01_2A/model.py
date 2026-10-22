"""固定真实高度、有限物距、色散 ASM 与固定中心测量。"""
import hashlib
import importlib.util
import math
import sys
import time
from pathlib import Path
import numpy as np
import torch
from scipy.ndimage import maximum_filter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from spiral_hsi.optics.phase_from_height import fused_silica, phase_from_height
from spiral_hsi.optics.propagation import asm as n00_asm

# 仅加载已核查的纯函数；关闭字节码写入由所有入口负责。
spec = importlib.util.spec_from_file_location('n01_baseline_model', ROOT/'experiments/N01_1/model.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
ring_charge = baseline.ring_charge
locate_peak = baseline.locate_peak
asm = baseline.asm_memory_bounded


def array_hash(value):
    return hashlib.sha256(np.ascontiguousarray(value,dtype=np.float64).tobytes()).hexdigest()


def validate_waves(waves):
    v = np.asarray(waves,dtype=np.float64)
    if v.ndim!=1 or not len(v) or not np.isfinite(v).all() or np.any(v<=0) or np.any(np.diff(v)<=0):
        raise ValueError('波长必须是严格递增的正有限一维列表')
    return v


def design(cfg,size=None,pitch=None):
    size = cfg['size'] if size is None else size
    pitch = cfg['pitch_um'] if pitch is None else pitch
    if size*pitch < cfg['diameter_um'] or pitch<=0:
        raise ValueError('采样必须覆盖同一真实孔径')
    c = (np.arange(size)-(size-1)/2)*pitch
    r2 = c[:,None]**2+c[None,:]**2
    aperture = r2 <= (cfg['diameter_um']/2)**2
    charge = ring_charge(np.sqrt(r2)/(cfg['diameter_um']/2),cfg['L'],cfg['epsilon'])
    azimuth = np.arctan2(c[:,None],c[None,:])
    f = cfg['focal_mm']*1000
    delta = float(fused_silica(cfg['design_nm']/1000))-cfg['n_env']
    focus_path = r2/(np.sqrt(f*f+r2)+f)
    focus = -2*np.pi/(cfg['design_nm']/1000)*focus_path
    spiral = charge*azimuth
    ideal = focus+spiral
    h2pi = (cfg['design_nm']/1000)/delta
    hW = np.where(aperture,h2pi/(2*np.pi)*np.remainder(ideal,2*np.pi),0.)
    R2 = (cfg['diameter_um']/2)**2
    hf = np.where(aperture,(R2-r2)/(np.sqrt(f*f+R2)+np.sqrt(f*f+r2))/delta,0.)
    hC = hf+np.where(aperture,h2pi/(2*np.pi)*np.remainder(spiral,2*np.pi),0.)
    for h in [hW,hC,hf]:
        h.setflags(write=False)
    return dict(coord=c,r2=r2,aperture=aperture,charge=charge,ideal=ideal,focus=focus,
                W=hW,C=hC,A=hf,h2pi_um=h2pi,size=size,pitch=pitch)


def phase_equivalence(d,cfg):
    mask=d['aperture']
    ideal=np.exp(1j*d['ideal'][mask])
    result={}
    for group in ['W','C']:
        actual=np.exp(1j*phase_from_height(d[group],cfg['design_nm'])[mask])
        factor=complex(np.mean(actual*np.conj(ideal)))
        factor=factor/abs(factor)
        residual=float(np.max(np.abs(actual/factor-ideal)))
        result[group]=dict(global_phase_rad=float(np.angle(factor)),max_residual=residual,
                           min_um=float(d[group][mask].min()),max_um=float(d[group][mask].max()),
                           sha256=array_hash(d[group]),outside_zero=bool(np.all(d[group][~mask]==0)),
                           nonnegative=bool(np.all(d[group]>=0)))
    result['W_direct_residual']=float(np.max(np.abs(np.exp(1j*phase_from_height(d['W'],550)[mask])-ideal)))
    result['h2pi_um']=d['h2pi_um']
    result['status']='PASS' if max(result['W_direct_residual'],result['C']['max_residual'])<=cfg['thresholds']['phase'] else 'FAIL'
    return result


def field(d,height,wave,cfg,diagnostic=None):
    s=cfg['object_cm']*10000
    distance=np.sqrt(s*s+d['r2'])
    amp=s/distance*d['aperture']
    amp=amp/np.sqrt(np.sum(amp**2)*d['pitch']**2)
    sphere=2*np.pi/(wave/1000)*d['r2']/(distance+s)
    phi=phase_from_height(height,wave)
    if diagnostic=='no_material_dispersion':
        phi=2*np.pi/(wave/1000)*(float(fused_silica(.55))-1)*height
    return torch.tensor(amp*np.exp(1j*(sphere+phi)),device=cfg['device'],dtype=torch.complex128)


def measure(image,c,cfg,wave):
    cfg_old=dict(wavelength_nm=wave,diameter_um=cfg['diameter_um'],roi_width_um=cfg['roi_width_um'],
                 pitch_um=1.,thresholds=dict(main_sidelobe_ratio_min=cfg['thresholds']['outside_disk_ratio']))
    result=baseline.analyze(image,c,cfg['sensor_mm'],cfg_old)
    row,col=np.unravel_index(image.argmax(),image.shape)
    result.update(argmax_row=int(row),argmax_col=int(col),argmax_x_um=float(c[col]),argmax_y_um=float(c[row]))
    yy,xx=np.meshgrid(c,c,indexing='ij')
    disk=(xx-result['peak_x_um'])**2+(yy-result['peak_y_um'])**2<=result['main_lobe_radius_um']**2
    maxima=(image==maximum_filter(image,size=3,mode='constant'))&~disk
    side_row,side_col=np.unravel_index(np.where(maxima,image,-1.).argmax(),image.shape)
    distinct=float(image[side_row,side_col]) if maxima.any() else 0.
    ratio=float(image.max()/distinct) if distinct>0 else None
    result.update(distinct_side_peak=distinct,distinct_side_ratio=ratio,
                  distinct_side_x_um=float(c[side_col]),distinct_side_y_um=float(c[side_row]))
    if ratio is not None and ratio<cfg['thresholds']['distinct_peak_ratio']:
        result['angle_valid']=False
        result['invalid_reason']+='；存在竞争的独立旁峰'
    if not result['subpixel_fit']:
        result['angle_valid']=False
        result['invalid_reason']+='；亚像素极值拟合不稳定'
    result['status']='VALID' if result['angle_valid'] else 'INVALID'
    return result


@torch.no_grad()
def propagate(d,height,wave,cfg,padding=None,full_path=None,diagnostic=None):
    start=time.perf_counter()
    hhash=array_hash(height)
    u=field(d,height,wave,cfg,diagnostic)
    input_energy=float(u.abs().square().sum())*d['pitch']**2
    torch.cuda.synchronize()
    propagation_start=time.perf_counter()
    pad=cfg['padding'] if padding is None else padding
    propagation_wave=cfg['design_nm'] if diagnostic=='fixed_propagation_wavelength' else wave
    output,spectral=asm(u,propagation_wave,d['pitch'],cfg['sensor_mm'],pad)
    del u
    intensity=output.abs().square()
    del output
    torch.cuda.synchronize()
    propagation_seconds=time.perf_counter()-propagation_start
    n=intensity.shape[0]
    total=float(intensity.sum())*d['pitch']**2
    def crop(width):
        count=int(round(width/d['pitch']))
        if count>n:
            return None
        top=(n-count)//2
        return intensity[top:top+count,top:top+count]
    roi=crop(cfg['roi_width_um']).cpu().numpy().copy()
    energy=float(roi.sum())*d['pitch']**2
    bands=int(round(16/d['pitch']))
    edge=intensity[:bands].sum()+intensity[-bands:].sum()+intensity[bands:-bands,:bands].sum()+intensity[bands:-bands,-bands:].sum()
    stats=dict(wavelength_nm=float(wave),n_silica=float(fused_silica(wave/1000)),height_sha256=hhash,
               pitch_um=d['pitch'],size=d['size'],padding=pad,raw_grid_size=n,
               input_energy=input_energy,raw_energy=total,crop_energy=energy,crop_fraction=energy/total,
               spectral_energy_accounting_error=abs(total-spectral['expected_output_energy'])/input_energy,
               global_peak_in_roi=bool(float(intensity.max())<=roi.max()*(1+1e-12)),
               edge_fraction=float(edge)*d['pitch']**2/total,**spectral,
               propagation_seconds=propagation_seconds,object_cm=cfg['object_cm'],sensor_mm=cfg['sensor_mm'],
               diagnostic=diagnostic)
    for width in [512,1024,2048]:
        patch=crop(width)
        stats[f'capture_{width}_um']=float(patch.sum())*d['pitch']**2/total if patch is not None else None
    c=(np.arange(roi.shape[0])-(roi.shape[0]-1)/2)*d['pitch']
    stats.update(measure(roi,c,cfg,wave))
    if not stats['global_peak_in_roi']:
        stats.update(angle_valid=False,status='INVALID',invalid_reason=stats['invalid_reason']+'；整域主峰在 ROI 外')
    stats['psf_centroid_x_um']=float(np.sum(roi*c[None,:])/roi.sum())
    stats['psf_centroid_y_um']=float(np.sum(roi*c[:,None])/roi.sum())
    if full_path is not None:
        np.save(full_path,intensity.cpu().numpy())
    del intensity
    assert hhash==array_hash(height)
    stats['seconds']=time.perf_counter()-start
    return roi,c,stats


def unwrap_segments(records,max_step=45):
    """过大角差标为连续性不确定；保留单图定位的有效性。"""
    previous=None
    segment=-1
    for row in records:
        row.update(angle_unwrapped_deg=None,segment=None,angle_step_deg=None,continuity='INVALID')
        if not row['angle_valid']:
            previous=None
            continue
        if previous is None:
            segment+=1
            value=row['angle_raw_deg']
        else:
            delta=(row['angle_raw_deg']-previous['angle_raw_deg']+180)%360-180
            if abs(delta)>max_step:
                segment+=1
                value=row['angle_raw_deg']
                row['continuity']='INCONCLUSIVE_JUMP'
            else:
                value=previous['angle_unwrapped_deg']+delta
                row['angle_step_deg']=delta
        row.update(angle_unwrapped_deg=value,segment=segment)
        if row['continuity']!='INCONCLUSIVE_JUMP':
            row['continuity']='VALID_SEGMENT'
        previous=row


def compare(base,b,other,o,coords,othercoords,cfg):
    if other.shape[0]==2*base.shape[0]:
        common=other.reshape(base.shape[0],2,base.shape[1],2).mean(axis=(1,3))
        assert np.allclose(othercoords.reshape(-1,2).mean(axis=1),coords,atol=1e-12)
    else:
        common=other
        assert np.array_equal(coords,othercoords)
    l1=float(np.abs(base/base.sum()-common/common.sum()).sum())
    shift=math.hypot(b['peak_x_um']-o['peak_x_um'],b['peak_y_um']-o['peak_y_um'])
    angle=abs((b['angle_raw_deg']-o['angle_raw_deg']+180)%360-180) if b['angle_valid'] and o['angle_valid'] else None
    energy_difference=abs(b['crop_energy']-o['crop_energy'])/b['input_energy']
    passed=l1<cfg['thresholds']['shape_l1'] and max(b['edge_fraction'],o['edge_fraction'])<cfg['thresholds']['edge'] and energy_difference<.01
    if b['angle_valid'] or o['angle_valid']:
        passed=passed and b['angle_valid'] and o['angle_valid'] and shift<cfg['thresholds']['shift_um'] and angle<cfg['thresholds']['angle_deg']
    return dict(shape_l1=l1,peak_shift_um=shift,angle_shift_deg=angle,
                captured_energy_difference=energy_difference,base_valid=b['angle_valid'],other_valid=o['angle_valid'],
                base_crop=b['crop_fraction'],other_crop=o['crop_fraction'],
                base_edge=b['edge_fraction'],other_edge=o['edge_fraction'],
                localization_applicable=bool(b['angle_valid'] or o['angle_valid']),
                status='PASS' if passed else 'FAIL')
