"""只读加载历史模型、逐例重建冻结观测，并保存可核查指纹。"""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'reports/N03/EXP3_UNKNOWN_POS_20261021_02'
CODE = Path(__file__).resolve().parent
NOTICE = 'EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL'
sys.path.insert(0, str(ROOT/'integration/single_spiral_to_hsi/n03_exp3'))
from forward_adapter import ForwardAdapter, f, noise, sampling


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def array_sha(a):
    return hashlib.sha256(a.tobytes()).hexdigest()


def write(path, obj):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False,
                  default=lambda v: v.item() if isinstance(v, np.generic) else str(v))


def text(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(value)


def csvread(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def csvwrite(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row)) or ['status']
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def gitstate():
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args])
    return dict(head=git('rev-parse', 'HEAD').decode().strip(),
                status=git('status', '--porcelain').decode('utf-8').strip(),
                tracked_diff_sha256=hashlib.sha256(git('diff', '--binary')).hexdigest())


def verify_baseline():
    required = ['DELIVERY.md', 'result_summary.md', 'run_config.json', 'pilot_gate.json',
                'metrics.csv', 'pilot_metrics.csv', 'optimization_traces.json',
                'stop_diagnosis.json', 'independent_audit.json', 'final_delivery_manifest.json',
                'source_manifest.json']
    missing = [name for name in required if not (BASE/name).is_file()]
    if missing:
        raise RuntimeError('STOP_DATA_REPRO: missing '+repr(missing))
    bad = [name for name, digest in read(BASE/'final_delivery_manifest.json').items()
           if not (BASE/name).is_file() or sha(BASE/name) != digest]
    bad += [name for name, digest in read(BASE/'source_manifest.json').items()
            if not (ROOT/name).is_file() or sha(ROOT/name) != digest]
    # 历史输入清单还覆盖了原前向、NNLS、采样接口及上游资产。
    historical = read(BASE/'input_manifest.json')
    bad += [name for name, entry in historical.items()
            if not (ROOT/name).is_file() or sha(ROOT/name) != entry['sha256']]
    if bad:
        raise RuntimeError('STOP_DATA_REPRO: frozen hash mismatch '+repr(bad))
    if sha(BASE/'metrics.csv') != sha(BASE/'pilot_metrics.csv'):
        raise RuntimeError('STOP_DATA_REPRO: pilot metrics differ')
    return dict(final_files=len(read(BASE/'final_delivery_manifest.json')),
                historical_inputs=len(historical), mismatches=[])


def prepare(model, config, oldrows):
    expected = [r for r in oldrows if r['method'] == 'O']
    if len(oldrows) != 144 or len(expected) != 48:
        raise RuntimeError('STOP_DATA_REPRO: historical case count')
    if not np.array_equal(model.weights, config['weights_RGB']):
        raise RuntimeError('STOP_DATA_REPRO: RGB weights')
    if model.pitch != config['detector']['pitch_um']:
        raise RuntimeError('STOP_DATA_REPRO: detector pitch')
    cases, manifest, operators = [], [], {}
    for r in expected:
        pi, si, seed = int(r['position_id']), int(r['spectrum_index']), int(r['seed'])
        position = config['positions'][pi]
        spectrum = config['spectra'][si]
        if pi not in config['pilot_positions'] or spectrum['name'] not in config['pilot_spectra']:
            raise RuntimeError('STOP_DATA_REPRO: unexpected case')
        if pi not in operators:
            a, capture = model.matrix(position)
            oracle_a, _ = model.matrix(position)
            oracle = f.Operator(oracle_a)
            fixed = f.Operator(model.matrix((0, 0))[0])
            operators[pi] = (a, capture, oracle, fixed)
        a, capture, oracle, fixed = operators[pi]
        truth = np.array(spectrum['truth'])
        clean = a@truth
        y = clean if seed == 0 else noise.protocol_q(
            clean, noise.gaussian_direction(seed, si, len(clean)), 40)[0]
        snr = noise.realized_snr(clean, y)
        fingerprint = array_sha(y-clean)
        case_id = f'pilot_{pi}_{si}_{seed}'
        if (case_id != r['observation'] or fingerprint != r['noise_sha256'] or
                not np.array_equal(truth, json.loads(r['truth'])) or
                position != [float(r['dx_true']), float(r['dy_true'])] or
                y.shape != (103788,) or y.dtype != np.float64 or
                (seed != 0 and abs(snr-40) > 1e-8)):
            raise RuntimeError('STOP_DATA_REPRO: observation '+case_id)
        y.setflags(write=False)
        cases.append(dict(id=case_id, source=r, y=y, clean=clean, truth=truth,
                          position=position, capture=capture, oracle=oracle, fixed=fixed,
                          snr=snr, y_sha256=array_sha(y), noise_sha256=fingerprint))
        manifest.append(dict(observation=case_id, protocol=r['protocol'], seed=seed,
                             spectrum=spectrum['name'], spectrum_index=si, position_id=pi,
                             true_position=position, truth=truth.tolist(),
                             y_sha256=array_sha(y), noise_sha256=fingerprint,
                             shape=list(y.shape), dtype=str(y.dtype), writeable=False,
                             actual_SNR_db=snr, y_norm=float(np.linalg.norm(y)),
                             y_sum=float(y.sum()), clean_sha256=array_sha(clean),
                             A_true_sha256=array_sha(a), capture=capture.tolist()))
    if len({c['id'] for c in cases}) != 48:
        raise RuntimeError('STOP_DATA_REPRO: duplicate cases')
    return cases, manifest
