"""N02 隔离物理模型；历史传播与检测函数仅只读导入。"""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path
import numpy as np
import torch
import yaml
from scipy import fft

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


frozen = module('n02_frozen_support', ROOT/'vendor_compat/experiments/N01_3A_G2_f2_q6_13wave/support.py')
legacy = frozen.legacy
p3 = frozen.p3
baseline = legacy.baseline
sys.path.insert(0, str(ROOT/'src'))
from spiral_hsi.optics.phase_from_height import phase_from_height
from spiral_hsi.optics.propagation import asm as core_asm


def config():
    return yaml.safe_load((ROOT/'configs/n02/baseline_B.yaml').read_text(encoding='utf-8'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def array_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def cauchy(w_um):
    return 1.5292 + .00800/np.asarray(w_um)**2


def design(cfg, spiral=True, continuous=False, soft_sigma=None):
    c = (np.arange(cfg['size'])-(cfg['size']-1)/2)*cfg['pitch_um']
    r2 = c[:, None]**2+c[None, :]**2
    mask = r2 <= cfg['R_um']**2
    v = r2/cfg['R_um']**2
    zone = np.minimum(np.floor(cfg['L']*v).astype(np.int32)+1, cfg['L'])
    theta = np.arctan2(c[:, None], c[None, :])
    f = cfg['focal_mm']*1000
    focus = -2*np.pi/(cfg['design_nm']/1000)*r2/(np.sqrt(f*f+r2)+f)
    psi = np.zeros_like(focus)
    low_fraction = None
    if spiral:
        if soft_sigma is None:
            psi = cfg['handedness']*zone*theta
        else:
            u = np.zeros_like(focus, dtype=np.complex128)
            for j in range(1, cfg['L']+1):
                u += np.exp(-(v-(j-.5)/cfg['L'])**2/(2*soft_sigma**2))*np.exp(1j*cfg['handedness']*j*theta)
            psi = np.angle(u)
            low_fraction = float(np.mean(np.abs(u[mask]) < .05))
    target = focus+psi
    period = cfg['design_nm']/1000/(float(cauchy(cfg['design_nm']/1000))-cfg['n_env'])
    h = period*np.remainder(target, 2*np.pi)/(2*np.pi)
    if not continuous:
        q = cfg['Q']
        levels = np.floor(q*h/period) if cfg['quantizer'] == 'floor' else np.floor(q*h/period+.5)
        # round 对照采用端点截断，明确不把顶级重新取模成零。
        h = period/q*np.clip(levels, 0, q-1)
    h = np.where(mask, h, 0.)
    h.setflags(write=False)
    return dict(coord=c, r2=r2, mask=mask, height=h, period_um=period,
                target=target, zone=zone, soft_low_amplitude_fraction=low_fraction)


def field(d, h, wave, cfg, material='cauchy', n_offset=0., tilt_mrad=0., source_sign=1):
    s = cfg['object_mm']*1000
    distance = np.sqrt(s*s+d['r2'])
    amp = s/distance*d['mask']
    unscaled_power = float((amp**2).sum()*cfg['pitch_um']**2)
    amp = amp/np.sqrt(unscaled_power)
    n = float(cauchy(wave/1000)) if material == 'cauchy' else float(cauchy(cfg['design_nm']/1000))
    phase = phase_from_height(h, wave, material_model=lambda _: n+n_offset, n_env=cfg['n_env'])
    phase += source_sign*2*np.pi/(wave/1000)*d['r2']/(distance+s)
    phase += 2*np.pi/(wave/1000)*(tilt_mrad/1000)*d['coord'][None, :]
    return amp*np.exp(1j*phase), unscaled_power


def independent_cpu(u, wave, cfg, padding=None, method='ASM'):
    """SciPy 独立传播；Fresnel 是传递函数近轴近似，单位全部为 µm。"""
    pad = cfg['padding'] if padding is None else padding
    n = u.shape[0]*pad
    a = np.zeros((n, n), np.complex128)
    t = (n-u.shape[0])//2
    a[t:t+u.shape[0], t:t+u.shape[0]] = u
    freq = fft.fftfreq(n, cfg['pitch_um'])
    f2 = freq[:, None]**2+freq[None, :]**2
    wl = wave/1000
    z = cfg['sensor_mm']*1000
    # 移除全局活塞可减少单精度相位误差，不改变任何强度。
    if method == 'Fresnel':
        transfer = np.exp(-1j*np.pi*wl*z*f2)
    else:
        q = 1/wl**2-f2
        root = np.sqrt(q.astype(np.complex128))
        transfer = np.exp(2j*np.pi*z*(root-1/wl))
    return np.abs(fft.ifft2(fft.fft2(a, workers=2)*transfer, workers=2))**2


def measure(raw, coord, rec, cfg, wave):
    oldcfg = dict(diameter_um=2*cfg['R_um'], sensor_mm=cfg['sensor_mm'], pitch_um=cfg['pitch_um'],
                  roi_width_um=cfg['roi_width_um'], thresholds=cfg['thresholds'])
    r = frozen.phase_free_record(raw, coord, rec, oldcfg, wave)
    proposal = bool(r['status']=='VALID' and r['main_sidelobe_ratio']>=1.5 and
                    (r['distinct_side_ratio'] is None or r['distinct_side_ratio']>=1.5))
    pixangle = math.degrees(math.atan2(r['argmax_y_um'], r['argmax_x_um']))
    r.update(candidate_id=cfg.get('candidate_id', 'B2'), n_lambda=rec.get('n_lambda',float(cauchy(wave/1000))),
        R_um=cfg['R_um'], f_mm=cfg['focal_mm'], object_distance_mm=cfg['object_mm'], sensor_z_mm=cfg['sensor_mm'],
        quantizer=cfg.get('quantizer'), Q=cfg.get('Q'), raw_total_energy=rec['raw_energy'],
        roi_energy_fraction=rec['crop_fraction'], main_lobe_energy_fraction=r['main_disk_energy_fraction_of_roi']*rec['crop_energy'],
        main_lobe_fraction_of_roi=r['main_disk_energy_fraction_of_roi'],
        main_peak_x_um=r['peak_x_um'], main_peak_y_um=r['peak_y_um'], radius_um=r['peak_radius_um'],
        raw_angle_deg=r['angle_raw_deg'], outside_main_disk_ratio=r['main_sidelobe_ratio'],
        fwhm_component_count=r['halfmax_components'], n01_status=r['status'],
        n02_status='PASS' if proposal else 'FAIL', validation_status='SIMULATED',
        pixel_fit_angle_error_proxy_deg=abs((r['angle_raw_deg']-pixangle+180)%360-180),
        uncertainty_reason='像素峰与亚像素峰角差仅为诊断代理，不是统计置信区间')
    return r


@torch.no_grad()
def propagate(d, h, wave, cfg, material='cauchy', n_offset=0., precision=128, method='ASM', tilt_mrad=0.):
    start = time.perf_counter()
    digest = array_sha(h)
    u, power = field(d, h, wave, cfg, material, n_offset, tilt_mrad)
    pitch = cfg['pitch_um']
    device = cfg['device']
    if method == 'Fresnel' or device == 'cpu_scipy':
        intensity = independent_cpu(u, wave, cfg, method=method)
        total = float(intensity.sum()*pitch**2)
        peak = float(intensity.max())
        spectral = dict(evanescent_input_fraction=0., expected_output_energy=1., evanescent_reason='当前采样 Nyquist 频率低于全部传播截止频率')
    else:
        dtype = torch.complex128 if precision == 128 else torch.complex64
        t = torch.as_tensor(u, dtype=dtype, device=device)
        if device == 'cuda':
            torch.cuda.reset_peak_memory_stats()
        if precision == 128:
            out, spectral = baseline.asm_memory_bounded(t, wave, pitch, cfg['sensor_mm'], cfg['padding'])
        else:
            out = core_asm(t, wave, pitch, cfg['sensor_mm'], cfg['padding'])
            spectral = dict(evanescent_input_fraction=0., expected_output_energy=1.)
        intensity = out.abs().square()
        del out, t
        total = float(intensity.sum())*pitch**2
        peak = float(intensity.max())
    n = intensity.shape[0]
    count = int(round(cfg['roi_width_um']/pitch))
    top = (n-count)//2
    patch = intensity[top:top+count, top:top+count]
    raw = patch.cpu().numpy().copy() if isinstance(patch, torch.Tensor) else patch.copy()
    b = max(1, int(round(16/pitch)))
    edge = intensity[:b].sum()+intensity[-b:].sum()+intensity[b:-b,:b].sum()+intensity[b:-b,-b:].sum()
    crop = float(raw.sum()*pitch**2)
    rec = dict(wavelength_nm=float(wave), input_energy=1., incident_unscaled_power_um2=power,
               raw_energy=total, crop_energy=crop, crop_fraction=crop/total,
               global_peak_in_roi=bool(raw.max()>=peak*(1-1e-12)), edge_fraction=float(edge)*pitch**2/total,
               spectral_energy_accounting_error=abs(total-spectral['expected_output_energy']),
               method=method, precision=precision, height_array_sha256=digest, **spectral)
    for width in [512,1024,2048]:
        k = int(round(width/pitch)); t0 = (n-k)//2
        rec[f'capture_{width}_um'] = float(intensity[t0:t0+k,t0:t0+k].sum())*pitch**2/total if k<=n else None
    del intensity, patch
    if device == 'cuda':
        torch.cuda.synchronize()
        rec['gpu_peak_allocated_bytes'] = torch.cuda.max_memory_allocated()
        rec['gpu_peak_reserved_bytes'] = torch.cuda.max_memory_reserved()
    coord = (np.arange(count)-(count-1)/2)*pitch
    rec = measure(raw, coord, rec, cfg, wave)
    rec.update(seconds=time.perf_counter()-start, max_height_um=float(h.max()),
               pitch_um=pitch, size=cfg['size'], padding=cfg['padding'], material=material, n_offset=n_offset,
               n_lambda=float(cauchy(wave/1000) if material=='cauchy' else cauchy(cfg['design_nm']/1000))+n_offset)
    assert array_sha(h) == digest, '传播修改了固定高度'
    return raw, coord, rec
