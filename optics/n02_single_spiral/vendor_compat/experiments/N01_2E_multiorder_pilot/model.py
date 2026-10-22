"""仅对原 C 型独立聚焦高度取模，原阶段模块只读复用。"""
import sys
sys.dont_write_bytecode = True
import importlib.util
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('n01_2a_readonly', ROOT/'experiments/N01_2A/model.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


def focus_spiral(d, cfg):
    """独立重建原螺旋项，再核对 C=A+spiral，保留原高度零点。"""
    azimuth = np.arctan2(d['coord'][:, None], d['coord'][None, :])
    spiral = np.where(d['aperture'], d['h2pi_um']/(2*np.pi)*
                      np.remainder(d['charge']*azimuth, 2*np.pi), 0.)
    focus = d['A']
    if not np.array_equal(focus+spiral, d['C']):
        raise ValueError('C 型独立分解不一致，停止')
    # 原传播函数内部省略 n_env 参数，只能在已确认空气配置下复用。
    if cfg['n_env'] != 1.0:
        raise ValueError('原传播接口与外部介质配置不匹配，停止')
    spiral.setflags(write=False)
    return focus, spiral


def a2_height(focus, spiral, mask, h2pi, m):
    if m not in (4, 8, 12, 16):
        raise ValueError('本轮仅允许 m=4、8、12、16')
    h = np.where(mask, np.remainder(focus, m*h2pi)+spiral, 0.)
    if h.ndim != 2 or not np.isrealobj(h) or not np.isfinite(h).all() or np.any(h < 0):
        raise ValueError('固定高度图必须为真实、有限、非负二维数组')
    h.setflags(write=False)
    return h
