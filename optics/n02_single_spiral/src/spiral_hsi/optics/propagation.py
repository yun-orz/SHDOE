import numpy as np
import torch
import torch.nn.functional as F


def pitch_pair(sampling_pitch_um):
    p = np.asarray(sampling_pitch_um, dtype=np.float64)
    if p.ndim == 0:
        p = np.repeat(p, 2)
    if p.shape != (2,) or not np.all(np.isfinite(p)) or np.any(p <= 0):
        raise ValueError('采样间距必须是正有限标量或 (dy,dx)，单位 µm')
    return float(p[0]), float(p[1])


@torch.no_grad()
def asm(field, wavelength_nm, sampling_pitch_um, propagation_distance_mm, padding=1):
    """独立 ASM：返回整个填充网格；周期边界，倏逝波指数衰减。"""
    if field.ndim != 2 or not field.is_complex() or not torch.isfinite(field).all():
        raise ValueError('场必须是有限二维复数张量')
    if not np.isfinite(wavelength_nm) or wavelength_nm <= 0:
        raise ValueError('波长必须为正有限值')
    if not np.isfinite(propagation_distance_mm) or propagation_distance_mm < 0:
        raise ValueError('仅支持非负有限传播距离，单位 mm')
    if not isinstance(padding, int) or padding < 1:
        raise ValueError('padding 必须为正整数倍率')
    dy, dx = pitch_pair(sampling_pitch_um)
    h, w = field.shape
    hp, wp = h * padding, w * padding
    field = F.pad(field, ((wp-w)//2, wp-w-(wp-w)//2, (hp-h)//2, hp-h-(hp-h)//2))
    if propagation_distance_mm == 0:
        return field
    rdtype = field.real.dtype
    fy = torch.fft.fftfreq(hp, d=dy, device=field.device, dtype=rdtype)
    fx = torch.fft.fftfreq(wp, d=dx, device=field.device, dtype=rdtype)
    q = (1 / (wavelength_nm / 1000.)**2 - fy[:, None]**2 - fx[None, :]**2)
    # 复数平方根使倏逝分量随正传播距离衰减，避免实数开根产生 NaN。
    kz = 2 * torch.pi * torch.sqrt(q.to(field.dtype))
    transfer = torch.exp(1j * propagation_distance_mm * 1000. * kz)
    return torch.fft.ifft2(torch.fft.fft2(field) * transfer)
