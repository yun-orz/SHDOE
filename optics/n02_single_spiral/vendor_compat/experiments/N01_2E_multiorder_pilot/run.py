"""有限样本入口：全部相位门通过后才进行至多十二次新传播。"""
import sys
sys.dont_write_bytecode = True
import argparse
import csv
import hashlib
import json
import platform
import subprocess
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from model import ROOT, legacy, focus_spiral, a2_height

EXP = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def save_case(path, raw, coords, record):
    with path.open('xb') as stream:
        np.savez_compressed(stream, raw_roi=raw, normalized_psf=raw/raw.sum(),
                            coords_um=coords, record_json=json.dumps(record, ensure_ascii=False))


def lobe_record(raw, coords, record, cfg, wave):
    record = dict(record)
    record.update(legacy.measure(raw, coords, cfg, wave))
    if not record['global_peak_in_roi']:
        record['angle_valid'] = False
        record['invalid_reason'] += '；整域主峰在ROI外'
    record['recognizable_single_lobe'] = bool(record['angle_valid'] and record['halfmax_components'] == 1)
    if record['halfmax_components'] != 1:
        record['invalid_reason'] += '；半峰连通域不唯一'
    record['status'] = 'VALID' if record['recognizable_single_lobe'] else 'INVALID'
    record['roi_99_percent_pass'] = bool(record['crop_fraction'] >= .99)
    return record


def plot_heights(out, heights, mask, coord):
    fig, axes = plt.subplots(1, 5, figsize=(17, 3.6), layout='constrained')
    vmax = float(heights['C'][mask].max())
    for ax, (name, height) in zip(axes, heights.items()):
        im = ax.imshow(np.where(mask, height, np.nan), origin='lower',
                       extent=[-1024, 1024, -1024, 1024], vmin=0, vmax=vmax, cmap='viridis')
        ax.set(title=name, xlabel='x (um)', ylabel='y (um)')
    fig.colorbar(im, ax=axes, label='Fixed physical height (um), common linear scale', shrink=.8)
    fig.savefig(out/'height_comparison.png', dpi=160)
    plt.close(fig)


def plot_psfs(out, rows, cases, names, waves):
    vmax = max(float(cases[(name, wave)].max()) for name in names for wave in waves)
    fig, axes = plt.subplots(3, 5, figsize=(17, 11), layout='constrained')
    for i, wave in enumerate(waves):
        for j, name in enumerate(names):
            ax = axes[i, j]
            raw = cases[(name, wave)]
            record = next(r for r in rows if r['group'] == name and r['wavelength_nm'] == wave)
            im = ax.imshow(raw, origin='lower', extent=[-256, 256, -256, 256],
                           vmin=0, vmax=vmax, cmap='inferno', interpolation='nearest')
            ax.set(title=f'{name} / {wave}nm / {record["status"]}', xlabel='x (um)', ylabel='y (um)')
            ax.plot(record['peak_x_um'], record['peak_y_um'], '+', color='cyan', ms=5)
            ax.axhline(0, lw=.3, color='white', alpha=.3)
            ax.axvline(0, lw=.3, color='white', alpha=.3)
            # 内嵌图仅放大固定中央范围，仍使用全图共同原始强度色标。
            inset = ax.inset_axes([.04, .04, .43, .43])
            inset.imshow(raw, origin='lower', extent=[-256, 256, -256, 256],
                         vmin=0, vmax=vmax, cmap='inferno', interpolation='nearest')
            inset.set(xlim=(-60, 60), ylim=(-60, 60), xticks=[], yticks=[])
            inset.set_title('+/-60um', fontsize=6, color='cyan', pad=1)
    fig.colorbar(im, ax=axes, label='Raw intensity / unit incident energy (um^-2); common linear scale', shrink=.65)
    fig.suptitle('Full 512um ROI; no per-image normalization; cyan = measured peak (invalid peaks diagnostic only)')
    fig.savefig(out/'psf_comparison.png', dpi=160)
    plt.close(fig)


def perform(out, pilot, cfg, ledger):
    started = time.perf_counter()
    paths = [EXP/'config.json', EXP/'model.py', EXP/'run.py', EXP/'verify.py', EXP/'README.md',
             ROOT/pilot['baseline_config'], ROOT/'experiments/N01_2A/model.py',
             ROOT/'experiments/N01_1/model.py', ROOT/'src/spiral_hsi/optics/phase_from_height.py',
             ROOT/'src/spiral_hsi/optics/propagation.py', ROOT/'src/spiral_hsi/optics/psf.py',
             ROOT/'experiments/N01_2D/config.json', ROOT/'results/N01_2A/metadata.json',
             ROOT/'results/N01_2A/artifact_manifest.json', ROOT/'results/N01_2A/height_C_um.npy',
             ROOT/'reports/N01_2A/N01_2A_固定高度DOE波长旋转可行性研究报告.md']
    baseline_paths = {w: ROOT/pilot['baseline_cases'].format(wave=w) for w in pilot['waves_nm']}
    paths += list(baseline_paths.values())
    inputs = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in paths}
    write_json(out/'input_hashes.json', inputs)
    manifest = json.loads((ROOT/'results/N01_2A/artifact_manifest.json').read_text(encoding='utf-8'))
    sealed = {v['path'].replace('\\', '/'): v['sha256'] for v in manifest['files']}
    # 旧模型与配置须和封存清单一致，避免用当前代码替旧来源自证。
    for p in paths:
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(('experiments/N01_2A/', 'results/N01_2A/')) and not rel.endswith('artifact_manifest.json'):
            if sealed.get(rel) != inputs[rel]:
                raise ValueError(f'旧基线封存哈希不一致或缺失：{rel}')
    oldmeta = json.loads((ROOT/'results/N01_2A/metadata.json').read_text(encoding='utf-8'))
    if oldmeta['config'] != cfg:
        raise ValueError('原配置与封存运行配置不一致')
    if not torch.cuda.is_available():
        raise RuntimeError('原CUDA环境不可用；不静默改为其他设备')
    d = legacy.design(cfg)
    focus, spiral = focus_spiral(d, cfg)
    archived = np.load(ROOT/'results/N01_2A/height_C_um.npy', allow_pickle=False)
    assert sha(ROOT/'results/N01_2A/height_C_um.npy') == pilot['expected_C_file_sha256']
    assert legacy.array_hash(d['C']) == pilot['expected_C_array_sha256']
    assert np.array_equal(archived, d['C'])
    del archived
    heights = {'C': d['C']}
    for m in pilot['m_values']:
        heights[f'A2_m{m}'] = a2_height(focus, spiral, d['aperture'], d['h2pi_um'], m)
    mask = d['aperture']
    cdepth = float(np.ptp(d['C'][mask]))
    phaseC = np.exp(1j*legacy.phase_from_height(d['C'], cfg['design_nm'], n_env=cfg['n_env']))
    hrows = []
    for name, height in heights.items():
        phase = np.exp(1j*legacy.phase_from_height(height, cfg['design_nm'], n_env=cfg['n_env']))
        err = float(np.max(np.abs(phase[mask]-phaseC[mask])))
        row = dict(group=name, m=0 if name == 'C' else int(name.split('m')[1]),
                   min_um=float(height[mask].min()), max_um=float(height[mask].max()),
                   depth_um=float(np.ptp(height[mask])), global_min_um=float(height.min()),
                   global_max_um=float(height.max()), phase_max_complex_error=err,
                   phase_pass=err <= pilot['phase_tolerance'], height_sha256=legacy.array_hash(height),
                   outside_zero=bool(np.all(height[~mask] == 0)), finite_nonnegative=bool(np.isfinite(height).all() and (height >= 0).all()))
        row['depth_reduction_percent'] = 100*(1-row['depth_um']/cdepth)
        hrows.append(row)
        np.save(out/f'height_{name}_um.npy', height, allow_pickle=False)
    np.savez_compressed(out/'height_components.npz', focus_um=focus, spiral_um=spiral,
                        aperture=mask, coords_um=d['coord'])
    write_csv(out/'height_metrics.csv', hrows)
    write_json(out/'phase_gate.json', hrows)
    if not all(r['phase_pass'] and r['outside_zero'] and r['finite_nonnegative'] for r in hrows):
        raise ValueError('550nm物理不变量未通过，停止后续传播')
    print('四个A2设计相位门通过；最大误差', max(r['phase_max_complex_error'] for r in hrows), flush=True)
    plot_heights(out, heights, mask, d['coord'])
    rows, cases = [], {}
    coords_expected = np.arange(512, dtype=np.float64)-255.5
    for wave, p in baseline_paths.items():
        with np.load(p, allow_pickle=False) as z:
            raw = z['raw_roi'].copy()
            coords = z['coords_um'].copy()
            rec = json.loads(z['record_json'].item())
            assert raw.dtype == np.float64 and raw.shape == (512, 512)
            assert np.array_equal(coords, coords_expected)
            assert np.isfinite(raw).all() and (raw >= 0).all()
            assert np.max(np.abs(z['normalized_psf']-raw/raw.sum())) < 1e-15
        expected = dict(wavelength_nm=wave, height_sha256=pilot['expected_C_array_sha256'],
                        pitch_um=cfg['pitch_um'], size=cfg['size'], padding=cfg['padding'],
                        raw_grid_size=cfg['size']*cfg['padding'], object_cm=cfg['object_cm'],
                        sensor_mm=cfg['sensor_mm'], diagnostic=None)
        assert all(rec[k] == value for k, value in expected.items())
        assert abs(raw.sum()*cfg['pitch_um']**2-rec['crop_energy']) < 1e-12
        assert abs(rec['crop_fraction']-rec['crop_energy']/rec['raw_energy']) < 1e-12
        rec = lobe_record(raw, coords, rec, cfg, wave)
        rec.update(group='C', source_path=p.relative_to(ROOT).as_posix(),
                   source_sha256=sha(p), reused=True, shape_l1_vs_C=0.)
        cases[('C', wave)] = raw
        rows.append(rec)
        save_case(out/'cases'/f'C_{wave}.npz', raw, coords, rec)
    torch.cuda.reset_peak_memory_stats()
    for name, height in heights.items():
        if name == 'C':
            continue
        for wave in pilot['waves_nm']:
            assert len(ledger) < pilot['max_propagations']
            entry = dict(group=name, wavelength_nm=wave, attempt=1)
            ledger.append(entry)
            with (out/'propagation_ledger.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(entry)+'\n')
            # 每个分支只运行一次，异常保留并停止，不降采样、不循环重试。
            raw, coords, rec = legacy.propagate(d, height, wave, cfg)
            assert np.array_equal(coords, coords_expected)
            rec = lobe_record(raw, coords, rec, cfg, wave)
            base = cases[('C', wave)]
            rec.update(group=name, reused=False, source_path='N01_2A.propagate (本轮调用)',
                       shape_l1_vs_C=float(np.abs(raw/raw.sum()-base/base.sum()).sum()))
            cases[(name, wave)] = raw
            rows.append(rec)
            save_case(out/'cases'/f'{name}_{wave}.npz', raw, coords, rec)
            print(f'{name} {wave}nm {rec["status"]} ROI={rec["crop_fraction"]:.6f} L1={rec["shape_l1_vs_C"]:.6g}', flush=True)
    write_csv(out/'psf_metrics.csv', rows)
    write_json(out/'psf_metrics.json', rows)
    plot_psfs(out, rows, cases, list(heights), pilot['waves_nm'])
    candidates = [m for m in pilot['m_values'] if all(r['recognizable_single_lobe'] for r in rows if r['group'] == f'A2_m{m}')]
    status = 'PILOT_PASS_CANDIDATES_FOUND' if candidates else 'PILOT_COMPLETE_NO_CANDIDATE'
    unchanged = all(sha(ROOT/rel) == digest for rel, digest in inputs.items())
    assert unchanged
    metadata = dict(status=status, candidate_m=candidates, pilot_config=pilot, baseline_config=cfg,
                    new_propagations=len(ledger), reused_C_cases=3, retry_count=0,
                    h2pi_um=d['h2pi_um'], command=subprocess.list2cmdline([sys.executable, '-B', *sys.argv]),
                    verification_command=f'"{sys.executable}" -B experiments/N01_2E_multiorder_pilot/verify.py "{out}"',
                    cwd=str(ROOT), time_Asia_Shanghai=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    git_status_before=(out/'git_status_before.txt').read_text(encoding='utf-8'),
                    python=sys.version, platform=platform.platform(), numpy=np.__version__, torch=torch.__version__,
                    gpu=torch.cuda.get_device_name(0), cuda=torch.version.cuda,
                    peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(),
                    elapsed_seconds=time.perf_counter()-started, input_hashes_unchanged=unchanged,
                    normalization='raw=|U|^2; input integral=1; normalized_psf=raw_roi/sum(raw_roi)',
                    energy_denominator='4096x4096有限周期FFT域，非无限空间效率',
                    height_statistics='min/max/depth在孔径内；另报全数组min/max；孔径外0非浮雕基底采样点',
                    single_lobe_rule=pilot['single_lobe_rule'])
    write_json(out/'metadata.json', metadata)
    text = ['# N01-2E 第一轮多阶包裹试验', '', f'结论：`{status}`。', '',
            '目标：仅包裹 C 型聚焦浮雕，保留八环带螺旋高度，检验降高与三波长形态。', '',
            '输入来源及逐文件 SHA256 见 `input_hashes.json`；封存 N01-2A 清单与重建 C 高度完全匹配。',
            'C 的 h_focus=A，h_spiral 由原电荷/方位角独立重建，逐位满足 C=focus+spiral。',
            f'外部介质 n_env={cfg["n_env"]}，h2π={d["h2pi_um"]:.12g}µm；未改材料、相位正号、入射场或探测面。', '',
            '环境：'+sys.version.split('\n')[0]+f'；torch {torch.__version__}；numpy {np.__version__}；'+torch.cuda.get_device_name(0),
            '实际命令（工程根目录执行）：', '```powershell', metadata['command'], metadata['verification_command'], '```',
            '复现须换用新的 `--run-id`，已有目录拒绝覆盖。', '',
            f'新增传播 {len(ledger)} 次，复用 C 3 个样本，重试0次；未执行其他波长、A1或下一阶段。',
            '输入2048²、pitch=1µm、padding=2、完整4096²；球面物距18cm、z=22.495mm；ROI512µm、原生像素无积分重采样。', '',
            '|结构|孔径内min µm|max µm|实际深度 µm|深度降低%|550nm最大复数误差|',
            '|---|---:|---:|---:|---:|---:|']
    for r in hrows:
        text.append(f'|{r["group"]}|{r["min_um"]:.9g}|{r["max_um"]:.9g}|{r["depth_um"]:.9g}|{r["depth_reduction_percent"]:.6f}|{r["phase_max_complex_error"]:.3g}|')
    text += ['', '高度统计使用孔径内真实采样极值，深度=max-min；全数组最小值0在CSV单列给出，未把孔径外0当浮雕最低点。',
             '四个m的float64设计复透射率门为最大绝对误差≤1e-6；直接比较C，不移除全局相位。', '',
             '|结构|nm|单主瓣|原始角°（无效仅诊断）|r µm|ROI/有限全域|主盘/ROI|L1 vs C|失败原因|',
             '|---|---:|---|---:|---:|---:|---:|---:|---|']
    for r in rows:
        text.append(f'|{r["group"]}|{r["wavelength_nm"]:g}|{r["status"]}|{r["angle_raw_deg"]:.5f}|{r["peak_radius_um"]:.5f}|{r["crop_fraction"]:.6f}|{r["main_disk_energy_fraction_of_roi"]:.6f}|{r["shape_l1_vs_C"]:.6g}|{r["invalid_reason"] or "无"}|')
    text += ['', '检测沿用原3×3对数二次定位、主盘外峰比≥1.25、独立旁峰比≥1.25、r>2µm、边界/全域峰/拟合检查，并要求半峰连通域唯一；未调阈值。',
             'L1是相同完整ROI内各自单位和形状的差异（范围0到2），未配准；ROI捕获使用原始强度/有限全域能量。',
             '图为共同原始强度线性色标，完整ROI±256µm，内嵌±60µm仍用相同色标；高度图也采用共同µm色标。', '',
             '失败与局限：所有未通过样本保留；99% ROI捕获检查见CSV，不作为形态成功的替代。',
             '仅三个波长且无新增收敛研究；有限周期FFT域能量不是绝对光学效率。薄相位忽略侧壁、内部传播与矢量效应；不作制造可行性结论。',
             '单主瓣可识别不等于能量集中或与C形态一致；三个点不证明全带旋转单调性、光谱分辨率或重建能力。', '',
             f'下一轮候选 m={candidates}。当前数据不足，暂不排序。只有独立批准后才考虑候选的31波长验证，本轮到此停止。',
             '独立最小核查见 `verification.json`（由单独核查命令生成，不增加传播次数）。', '']
    with (out/'summary.md').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(text))
    print(status, 'candidates=', candidates, 'new_propagations=', len(ledger), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.run_id):
        raise ValueError('run-id只允许英数字、下划线和连字符')
    out = ROOT/'results/N01_2E_multiorder_pilot'/args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out/'cases').mkdir()
    (out/'git_status_before.txt').write_text(subprocess.check_output(['git', 'status', '--short', '--untracked-files=normal'], cwd=ROOT, text=True, encoding='utf-8'), encoding='utf-8')
    pilot = json.loads((EXP/'config.json').read_text(encoding='utf-8'))
    cfg = json.loads((ROOT/pilot['baseline_config']).read_text(encoding='utf-8'))
    write_json(out/'config.json', {'pilot': pilot, 'baseline': cfg})
    ledger = []
    try:
        perform(out, pilot, cfg, ledger)
    except Exception as exc:
        write_json(out/'failure.json', dict(status='BLOCKED_OR_INCOMPLETE', error=str(exc),
                   traceback=traceback.format_exc(), attempted_propagations=len(ledger), retries=0))
        if not (out/'summary.md').exists():
            (out/'summary.md').write_text(f'# N01-2E\n\nBLOCKED_OR_INCOMPLETE\n\n原因：{exc}\n\n已尝试传播{len(ledger)}次；未重试。详见failure.json。停止后续计算，保留失败产物。\n', encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
