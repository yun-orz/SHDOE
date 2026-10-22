import numpy as np

MATERIAL_SOURCE = 'https://opg.optica.org/josa/abstract.cfm?uri=josa-55-10-1205'


def fused_silica(wavelength_um):
    """Malitson 1965，20 摄氏度，波长单位 µm。"""
    w = np.asarray(wavelength_um, dtype=np.float64)
    if not np.all(np.isfinite(w)) or np.any((w < .21) | (w > 3.71)):
        raise ValueError('材料波长必须在 0.21–3.71 µm 内且有限')
    b = np.array([.6961663, .4079426, .8974794])
    c = np.array([.0684043, .1162414, 9.896161]) ** 2
    return np.sqrt(1 + np.sum(b * w[..., None]**2 / (w[..., None]**2 - c), axis=-1))


def phase_from_height(height_um, wavelength_nm, material_model=fused_silica, n_env=1.):
    """直接由未包裹实体高度计算弧度相位，不在跨波长之前取模。"""
    h = np.asarray(height_um, dtype=np.float64)
    if h.ndim != 2 or not np.all(np.isfinite(h)) or np.any(h < 0):
        raise ValueError('height_um 必须是非负有限的二维高度图')
    if not np.isscalar(wavelength_nm) or not np.isfinite(wavelength_nm) or wavelength_nm <= 0:
        raise ValueError('波长必须为正有限标量，单位 nm')
    if not np.isfinite(n_env) or n_env <= 0:
        raise ValueError('环境折射率必须为正有限标量')
    w = wavelength_nm / 1000.
    n = float(material_model(w))
    if not np.isfinite(n) or n <= 0:
        raise ValueError('材料折射率必须为正有限值')
    return (2 * np.pi / w) * (n - n_env) * h
