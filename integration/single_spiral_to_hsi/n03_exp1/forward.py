"""已知轴上点源：在固定物理ROI直接叠加强度，不调用图像卷积。"""
import json
import numpy as np

WAVELENGTHS = np.arange(420, 661, 30, dtype=float)
MODELS = ['B0_RGB_delta', 'B1_fixed_PSF', 'B2_spiral_PSF']


def load_assets(root):
    base = root / 'optics/n02_single_spiral/results/n02/n02_20261019_02/B2'
    kernels, paths, records = [], [], []
    for wave in WAVELENGTHS:
        path = base / 'cases' / f'{wave:g}nm.npz'
        with np.load(path, allow_pickle=False) as z:
            h, coord = z['normalized_psf'].copy(), z['coords_um']
            rec = json.loads(z['record_json'].item())
            assert rec['wavelength_nm'] == wave and rec['pitch_um'] == 1
            assert h.shape == (512, 512) and h.dtype == np.float64
            assert np.array_equal(coord, np.arange(512) - 255.5)
            assert np.isfinite(h).all() and h.min() >= 0 and abs(h.sum()-1) < 1e-12
            assert np.max(abs(h-z['raw_roi']/z['raw_roi'].sum())) < 1e-15
            kernels.append(h); paths.append(path); records.append(rec)
    sensor_path = root / 'framework/DeepLensHSI/sensors/flir/BFS-U3-200S7C-C.json'
    sensor = json.loads(sensor_path.read_text(encoding='utf-8'))
    source_nm = np.array(sensor['wavelengths']) * 1000
    indices = []
    for wave in WAVELENGTHS:
        hits = np.flatnonzero(np.isclose(source_nm, wave, rtol=0, atol=1e-9))
        assert len(hits) == 1
        indices.append(int(hits[0]))
    full = np.array([sensor[c+'_response'] for c in ['red', 'green', 'blue']], dtype=float)
    weights = full[:, indices] / full[1].sum()
    assert weights.shape == (3, 9) and np.isfinite(weights).all() and weights.min() >= 0
    spiral = np.stack(kernels)
    delta = np.zeros_like(spiral)
    # 偶数网格无中心像元：统一指定右上邻轴心的(+0.5,+0.5)um像元，所有波长相同。
    delta[:, 256, 256] = 1
    fixed = np.broadcast_to(spiral[4], spiral.shape)
    return dict(zip(MODELS, [delta, fixed, spiral])), weights, paths+[sensor_path], records, indices


def point_matrix(kernels, weights):
    """按RGB、行、列的C顺序展平，波长作为列。"""
    return (weights[:, :, None] * kernels.reshape(len(kernels), -1)[None, :, :]).transpose(0, 2, 1).reshape(-1, len(kernels))


def render_multiband(spectrum, kernels, weights):
    """独立逐波长、逐通道累加路径，不访问A或point_matrix。"""
    image = np.zeros((3, *kernels.shape[1:]), dtype=np.float64)
    for band, strength in enumerate(spectrum):
        for channel in range(3):
            image[channel] += strength * weights[channel, band] * kernels[band]
    return image


def render_one_hot(band, kernels, weights):
    spectrum = np.zeros(len(kernels)); spectrum[band] = 1
    return render_multiband(spectrum, kernels, weights)
