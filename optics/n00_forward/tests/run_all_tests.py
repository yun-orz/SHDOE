"""T01–T04 小尺寸与收敛验证，失败返回非零退出码。"""
import json
import math
import sys
import traceback
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.special import j1

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from spiral_hsi.optics.phase_from_height import phase_from_height, fused_silica
from spiral_hsi.optics.propagation import asm
from spiral_hsi.optics.psf import compute_psf, reference_doe, array_hash
OUT = ROOT/'results'/'N00'
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = {}


def reject(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError('错误输入未被拒绝')


def t01():
    h = np.zeros((8,8))
    assert np.array_equal(phase_from_height(h, 550), h)
    for wave in [0, -1, np.nan, np.inf]:
        reject(lambda: phase_from_height(h, wave))
    for bad in [np.ones(8), np.full((8,8), np.nan), -np.ones((8,8))]:
        reject(lambda: phase_from_height(bad, 550))
    field = torch.ones((128,128), dtype=torch.complex128)
    for z in [-1, np.inf, np.nan]:
        reject(lambda: asm(field, 550, 1, z))
    for pitch in [0, -1, np.inf, (1, np.nan), (1,2,3)]:
        reject(lambda: asm(field, 550, pitch, 1))
    reject(lambda: compute_psf(h, [550], np.ones((7,8)), device='cpu'))
    reject(lambda: compute_psf(h, [550,400], np.ones_like(h), device='cpu'))
    return dict(zero_phase_max=0., nm_to_um=550/1000, mm_to_um=1*1000, invalid_inputs='已拒绝')


def t02():
    h = np.array([[0., .123],[1.7, 20.]])
    before = array_hash(h)
    records = []
    for wave in [400.,550.,700.]:
        w = wave/1000
        n = math.sqrt(1 + .6961663*w*w/(w*w-.0684043**2) + .4079426*w*w/(w*w-.1162414**2) + .8974794*w*w/(w*w-9.896161**2))
        expected = np.array([[2*math.pi/w*(n-1)*float(v) for v in row] for row in h])
        phi = phase_from_height(h, wave)
        error = float(np.max(np.abs(phi-expected)))
        wrapped_error = float(np.max(np.abs(np.exp(1j*phi)-np.exp(1j*np.remainder(phi,2*np.pi)))))
        assert error < 1e-12 and wrapped_error < 1e-12
        records.append(dict(wavelength_nm=wave, phase=phi.tolist(), expected=expected.tolist(), abs_error=error, exp_wrapped_error=wrapped_error))
    assert array_hash(h)==before
    return dict(comparisons=records, height_sha256=before, height_unchanged=True)


def t03():
    rng = np.random.default_rng(20261009)
    a = rng.normal(size=(128,128))+1j*rng.normal(size=(128,128))
    u = torch.tensor(a, dtype=torch.complex128)
    identity_error = float(torch.max(torch.abs(asm(u,550,1.,0.)-u)))
    fft_identity_error = float(torch.max(torch.abs(torch.fft.ifft2(torch.fft.fft2(u))-u)))
    v = asm(u,550,1.,.2)
    energy_error = abs(float(v.abs().square().sum()/u.abs().square().sum())-1)
    plane = torch.ones((128,128), dtype=torch.complex128)
    plane_out = asm(plane,550,1.,.2)
    plane_error = float((plane_out.abs().square()-1).abs().max())
    assert identity_error < 1e-12 and fft_identity_error < 1e-12 and energy_error < 1e-12 and plane_error < 1e-12
    # 各向异性矩形网格上的单频平面波核查方向与单位。
    yy,xx = np.indices((128,256))
    mode = torch.tensor(np.exp(2j*np.pi*(3*yy/128+5*xx/256)), dtype=torch.complex128)
    predicted = np.exp(2j*np.pi*200*np.sqrt(1/.55**2-(3/(128*2))**2-(5/256)**2))
    mode_error = float(torch.max(torch.abs(asm(mode,550,(2,1),.2)-mode*predicted)))
    assert mode_error < 1e-10
    h,ap = reference_doe()
    result = compute_psf(h,[550],ap, device='cuda')
    center = result['raw_intensity'][0][512,512:552]
    r = np.sqrt((np.arange(40)+.5)**2+.5**2)
    q = 2*np.pi*64*r/(.55*1000)
    airy = (2*j1(q)/q)**2
    center = center/center[0]; airy=airy/airy[0]
    rms = float(np.sqrt(np.mean((center-airy)**2)))
    assert rms < .02
    fig,ax=plt.subplots(1,2,figsize=(10,4))
    ax[0].imshow(result['raw_intensity'][0][472:552,472:552], extent=[-40,40,-40,40],origin='lower'); ax[0].set_title('550 nm physical ASM'); ax[0].set_xlabel('x (um)'); ax[0].set_ylabel('y (um)')
    ax[1].plot(r,center,label='ASM'); ax[1].plot(r,airy,'--',label='Paraxial Airy reference'); ax[1].legend(); ax[1].set_xlabel('radius (um)')
    fig.tight_layout(); fig.savefig(OUT/'t03_analytical_airy_validation.png',dpi=160); plt.close(fig)
    return dict(identity_abs_error=identity_error, fft_identity_abs_error=fft_identity_error, energy_relative_error=energy_error, plane_intensity_error=plane_error,
                rectangular_mode_abs_error=mode_error, airy_profile_rms=rms, airy_rms_limit=.02,
                aperture_energy=result['raw_energy_stats'][0], small_grid=128)


def t04():
    records=[]
    for wave in [400,550,700]:
        datasets=[]
        for size,pitch,pad,crop in [(256,1.,4,512),(256,1.,6,512),(512,.5,4,1024)]:
            h,a=reference_doe(size,pitch)
            r=compute_psf(h,[wave],a,sampling_pitch_um=pitch,padding=pad,crop=crop,device='cuda')
            data=r['PSF_cube'][0]
            if pitch==.5:
                # 对齐同一物理像素覆盖范围，积分细网格强度；仅供收敛比较。
                data=data.reshape(512,2,512,2).sum(axis=(1,3))
            datasets.append((data,r['raw_energy_stats'][0]))
        base=datasets[0][0]
        indices=np.arange(512)-255.5
        peak0=np.array(np.unravel_index(base.argmax(),base.shape))
        for i,label in [(1,'padding_4_vs_6'),(2,'pitch_1_vs_0.5_um')]:
            other=datasets[i][0]
            l1=float(np.abs(base-other).sum())
            centroid=[float((other.sum(axis=1)*indices).sum()),float((other.sum(axis=0)*indices).sum())]
            peak=np.array(np.unravel_index(other.argmax(),other.shape))
            peak_distance=float(np.linalg.norm(peak-peak0))
            fractions=[datasets[j][1]['crop_fraction'] for j in [0,i]]
            energy_difference=abs(datasets[0][1]['crop_energy']-datasets[i][1]['crop_energy'])/datasets[i][1]['crop_energy']
            rec=dict(wavelength_nm=wave,comparison=label, normalized_l1=l1, centroid_um=centroid,
                     peak_distance_um=peak_distance,crop_fractions=fractions, relative_captured_energy_difference=energy_difference,
                     base_stats=datasets[0][1], comparison_stats=datasets[i][1])
            records.append(rec)
            assert l1 < .05 and peak_distance <= 2 and min(fractions)>.99 and energy_difference < .01
            assert max(datasets[j][1]['edge_fraction'] for j in [0,i]) < .001
    return dict(records=records, limits=dict(shape_l1=.05,peak_um=2.,crop_fraction_min=.99,captured_energy_difference=.01,edge_fraction=.001))


if __name__=='__main__':
    for key,fn in [('T01',t01),('T02',t02),('T03',t03),('T04',t04)]:
        try:
            RESULTS[key]=dict(status='PASS',evidence=fn())
            print(key, 'PASS', flush=True)
        except Exception:
            RESULTS[key]=dict(status='FAIL',traceback=traceback.format_exc())
            print(RESULTS[key]['traceback'],flush=True)
            break
    (OUT/'preflight_summary.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(0 if len(RESULTS)==4 and all(v['status']=='PASS' for v in RESULTS.values()) else 1)
