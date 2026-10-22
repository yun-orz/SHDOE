import hashlib
import time
import numpy as np
import torch
from .phase_from_height import phase_from_height, fused_silica, MATERIAL_SOURCE
from .propagation import asm, pitch_pair


def array_hash(a):
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def reference_doe(size=256, pitch_um=1., radius_um=64., focal_mm=1., design_nm=550.):
    """未包裹的解析聚焦浮雕，孔径外高度为零；参数是 N00 对照规格。"""
    c = (np.arange(size) - (size-1)/2) * pitch_um
    r2 = c[:, None]**2 + c[None, :]**2
    aperture = (r2 <= radius_um**2).astype(np.float64)
    f = focal_mm * 1000.
    height = np.maximum(0., (np.sqrt(f*f + radius_um**2) - np.sqrt(f*f + r2)) / (float(fused_silica(design_nm / 1000.))-1)) * aperture
    return height, aperture


@torch.no_grad()
def compute_psf(height_um, wavelength_nm, aperture_mask, material_model=fused_silica,
                sampling_pitch_um=1., propagation_distance_mm=1., incident_condition='plane_wave',
                axis='on_axis', padding=4, crop=512, sensor_sampling='native', device='cuda'):
    """返回归一化 PSF、裁剪前绝对强度、能量记录及完整接口元数据。"""
    h = np.asarray(height_um, dtype=np.float64)
    a = np.asarray(aperture_mask, dtype=np.float64)
    waves = np.asarray(wavelength_nm, dtype=np.float64)
    if waves.ndim != 1 or not len(waves) or not np.all(np.isfinite(waves)) or np.any(waves <= 0) or np.any(np.diff(waves) <= 0):
        raise ValueError('波长列表必须非空、正有限、严格递增')
    if a.shape != h.shape or a.ndim != 2 or not np.all(np.isfinite(a)) or np.any((a<0)|(a>1)) or not np.any(a):
        raise ValueError('振幅光瞳须与高度同形、有限、在 [0,1] 且非空')
    if incident_condition != 'plane_wave' or axis != 'on_axis' or sensor_sampling != 'native':
        raise ValueError('N00 仅支持轴上平面波和原生传感器网格，无插值')
    if not isinstance(padding, int) or padding < 1 or not isinstance(crop, int) or crop <= 0 or crop > min(h.shape)*padding:
        raise ValueError('填充或裁剪尺寸非法')
    dy, dx = pitch_pair(sampling_pitch_um)
    phase_from_height(h, waves[0], material_model)
    before = array_hash(h)
    amp = torch.as_tensor(a, dtype=torch.float64, device=device)
    raw, cube, stats = [], [], []
    for wave in waves:
        if device.startswith('cuda'):
            torch.cuda.synchronize()
        start = time.perf_counter()
        phi = torch.as_tensor(phase_from_height(h, float(wave), material_model), device=device)
        field = amp * torch.exp(1j * phi)
        out = asm(field, float(wave), (dy, dx), propagation_distance_mm, padding)
        intensity = out.abs().square()
        ih, iw = intensity.shape
        top, left = (ih-crop)//2, (iw-crop)//2
        patch = intensity[top:top+crop, left:left+crop]
        inp = float(amp.square().sum()) * dx * dy
        total = float(intensity.sum()) * dx * dy
        captured = float(patch.sum()) * dx * dy
        if captured <= 0 or not np.isfinite(captured):
            raise ValueError('裁剪能量必须为正有限值')
        edge = intensity[:8].sum()+intensity[-8:].sum()+intensity[8:-8,:8].sum()+intensity[8:-8,-8:].sum()
        raw.append(intensity.cpu().numpy())
        cube.append((patch/patch.sum()).cpu().numpy())
        if device.startswith('cuda'):
            torch.cuda.synchronize()
        stats.append(dict(wavelength_nm=float(wave), n=float(material_model(wave/1000.)), input_energy=inp,
                          output_energy=total, crop_energy=captured, crop_fraction=captured/total,
                          energy_relative_error=abs(total-inp)/inp, edge_fraction=float(edge)*dx*dy/total,
                          seconds=time.perf_counter()-start, height_sha256=before))
        del phi, field, out, intensity, patch
    if before != array_hash(h):
        raise RuntimeError('共享高度图被修改')
    metadata = dict(height_unit='um', wavelength_unit='nm', phase_unit='rad', distance_unit='mm',
                    material_model=getattr(material_model, '__name__', str(material_model)),
                    material_source=MATERIAL_SOURCE if material_model is fused_silica else '调用方提供',
                    height_sha256=before, aperture_sha256=array_hash(a), aperture_role='amplitude_transmission',
                    sampling_pitch_um=[dy,dx], propagation_distance_mm=propagation_distance_mm,
                    incident_condition=incident_condition, axis=axis, padding=padding, crop=crop,
                    sensor_sampling=sensor_sampling, normalized_after_crop=True, device=device,
                    dtype='float64/complex128', raw_grid_shape=list(raw[0].shape),
                    energy_units='relative incident intensity times um^2', n_env=1.,
                    boundary='zero padded input, periodic FFT domain', evanescent='exponential decay',
                    raw_origin_pixel=[(raw[0].shape[0]-1)/2,(raw[0].shape[1]-1)/2])
    return dict(PSF_cube=np.stack(cube), raw_intensity=np.stack(raw), raw_energy_stats=stats,
                wavelength_nm=waves, metadata=metadata)
