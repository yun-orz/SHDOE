"""不调用优化器的独立逐行指标、配对统计和硬门核验。"""
import json
import math
import statistics
from frozen_pilot import csvread, csvwrite, write

METRICS = ['position_error_pixel', 'position_error_um', 'position_error_nm',
           'NRMSE', 'SAM_deg', 'energy_bias', 'relative_residual', 'nnls_KKT', 'seconds']
HISTORY_KEYS = ['dx_true', 'dy_true', 'dx_hat', 'dy_hat', 'position_error_pixel',
                'position_error_nm', 'NRMSE', 'SAM_deg', 'energy_bias',
                'relative_residual', 'y_norm', 'recovered_energy', 'kkt']
TOLERANCE = dict(absolute=1e-12, relative=1e-10, SAM_deg_absolute=2e-6)


def close(a, b, key=''):
    return math.isclose(float(a), float(b), rel_tol=TOLERANCE['relative'],
                        abs_tol=TOLERANCE['SAM_deg_absolute'] if key == 'SAM_deg'
                        else TOLERANCE['absolute'])


def regression(current, historical):
    index = {(r['observation'], r['method']): r for r in historical}
    results = []
    for r in current:
        old = index[(r['observation'], r['method'])]
        differences = {k: float(r[k])-float(old[k]) for k in HISTORY_KEYS}
        mismatches = [k for k in HISTORY_KEYS if not close(r[k], old[k], k)]
        for key in ['truth', 'estimate', 'capture']:
            a, b = json.loads(r[key]), json.loads(old[key])
            if len(a) != len(b) or any(not close(x, y) for x, y in zip(a, b)):
                mismatches.append(key)
        for key in ['noise_sha256', 'protocol', 'spectrum', 'seed', 'position_id', 'evaluations']:
            if str(r[key]) != str(old[key]):
                mismatches.append(key)
        results.append(dict(observation=r['observation'], method=r['method'],
                            passed=not mismatches, mismatches=json.dumps(mismatches),
                            **{'delta_'+k: v for k, v in differences.items()}))
    return results


def percentile(a, p=.9):
    a = sorted(a)
    h = p*(len(a)-1)
    lo, hi = math.floor(h), math.ceil(h)
    return a[lo]+(a[hi]-a[lo])*(h-lo)


def aggregate(rows):
    groups = {}
    for r in rows:
        for dimension, value in [('ALL', 'ALL'), ('kind', r['kind']),
                                 ('position', str(r['position_id'])), ('seed', str(r['seed']))]:
            key = (r['budget_group'], r['protocol'], r['method'], dimension, value)
            groups.setdefault(key, []).append(r)
    result = []
    for key, items in groups.items():
        entry = dict(zip(['budget_group', 'protocol', 'method', 'dimension', 'group'], key))
        entry['n'] = len(items)
        for metric in METRICS:
            values = [float(r[metric]) for r in items]
            for suffix, number in [('mean', statistics.fmean(values)),
                                   ('median', statistics.median(values)),
                                   ('p90', percentile(values)), ('max', max(values)),
                                   ('max_abs', max(map(abs, values)))]:
                entry[metric+'_'+suffix] = number
        entry['fraction_NRMSE_le_0.01'] = sum(float(r['NRMSE']) <= .01 for r in items)/len(items)
        result.append(entry)
    return result


def paired(rows):
    index = {(r['budget_group'], r['observation'], r['method']): r for r in rows}
    results, controls = [], []
    for (group, obs, method), a in index.items():
        if group != 'A':
            continue
        b = index[('B', obs, method)]
        entry = dict(observation=obs, method=method, protocol=a['protocol'], spectrum=a['spectrum'],
                     position_id=a['position_id'], seed=a['seed'], y_sha256=a['y_sha256'],
                     same_y=a['y_sha256'] == b['y_sha256'],
                     time_ratio_B_over_A=float(b['seconds'])/max(float(a['seconds']), 1e-300))
        for key in METRICS:
            entry[key+'_A'] = a[key]
            entry[key+'_B'] = b[key]
            entry[key+'_B_minus_A'] = float(b[key])-float(a[key])
        for key in ['dx_true', 'dy_true', 'dx_hat', 'dy_hat', 'estimate',
                    'selected_candidate_converged', 'joint_optimizer_status']:
            entry[key+'_A'], entry[key+'_B'] = a[key], b[key]
        for group_name in ['A', 'B']:
            own = index[(group_name, obs, method)]
            for ref in ['O', 'F']:
                for metric in ['NRMSE', 'SAM_deg', 'relative_residual']:
                    entry[f'{group_name}_{metric}_minus_{ref}'] = float(own[metric])-float(index[(group_name, obs, ref)][metric])
        results.append(entry)
        if method != 'J':
            checks = [close(a[k], b[k], k) for k in HISTORY_KEYS]
            checks.append(json.loads(a['estimate']) == json.loads(b['estimate']))
            controls.append(dict(observation=obs, method=method, passed=all(checks), same_y=entry['same_y']))
    return results, controls


def true_value(value):
    return value is True or value == 'True'


def gates(rows, h0, h1, integrity, controls):
    b = [r for r in rows if r['budget_group'] == 'B' and r['method'] == 'J']
    clean = [r for r in b if r['protocol'] == 'noiseless']
    noisy = [r for r in b if r['protocol'] == 'Q40']
    out = {'H0': dict(passed=h0, definition='48观测指纹一致且A的144行历史回归通过'),
           'H1': dict(passed=h1, definition='仅maxfev55→150；真值隔离；同一只读y'),
           'H2': dict(passed=len(clean) == 24 and all(float(r['position_error_pixel']) <= .005 for r in clean),
                      passed_cases=sum(float(r['position_error_pixel']) <= .005 for r in clean), total=len(clean), threshold=.005),
           'H3': dict(passed=len(noisy) == 24 and all(float(r['position_error_pixel']) <= .02 for r in noisy),
                      passed_cases=sum(float(r['position_error_pixel']) <= .02 for r in noisy), total=len(noisy), threshold=.02)}
    fractions = {p: sum(float(r['NRMSE']) <= .01 for r in rs)/len(rs) if rs else 0
                 for p, rs in [('noiseless', clean), ('Q40', noisy)]}
    out['H4'] = dict(passed=all(v >= .8 for v in fractions.values()), fractions=fractions,
                     NRMSE_threshold=.01, fraction_threshold=.8)
    valid = [r for r in b if true_value(r['joint_numerically_accepted'])]
    out['H5'] = dict(passed=len(valid) == 48, accepted=len(valid), total=len(b),
                     definition='选中缓存点与成功Powell返回终点逐位相同，且NNLS有限非负/KKT合格')
    count_ok = len(rows) == 288 and len({(r['budget_group'], r['observation'], r['method']) for r in rows}) == 288
    boundary = [r['observation'] for r in b if true_value(r['position_boundary_hit'])]
    of_ok = len(controls) == 96 and all(r['passed'] and r['same_y'] for r in controls)
    out['H6'] = dict(passed=integrity and count_ok and not boundary and of_ok,
                     unchanged=integrity, complete=count_ok, boundary_cases=boundary, OF_invariant=of_ok)
    for name, rs, limit in [('clean', clean, .005), ('Q40', noisy, .02)]:
        out['violations_'+name] = [r['observation'] for r in rs if float(r['position_error_pixel']) > limit]
    out['full'] = dict(status='NOT_RUN', observations=0, planned=504)
    out['upstream'] = {'N03_G0': 'FAIL', 'N02_G2': 'FAIL', 'N02_G3_Numerics': 'FAIL'}
    out['decision'] = 'EXP3R_PILOT_COMPUTATIONAL_PASS' if all(out[k]['passed'] for k in ['H0','H1','H2','H3','H4','H5','H6']) else 'EXP3R_PILOT_FAIL'
    return out


def audit_rows(rows, pitch):
    failures = []
    for r in rows:
        obs = r['budget_group']+'/'+r['observation']+'/'+r['method']
        truth, estimate = json.loads(r['truth']), json.loads(r['estimate'])
        nrmse = math.sqrt(sum((x-y)**2 for x, y in zip(truth, estimate))/sum(x*x for x in truth))
        ep = math.hypot(float(r['dx_hat'])-float(r['dx_true']), float(r['dy_hat'])-float(r['dy_true']))
        for key, number in [('NRMSE', nrmse), ('position_error_pixel', ep),
                            ('position_error_um', ep*pitch), ('position_error_nm', ep*pitch*1000)]:
            if not close(r[key], number):
                failures.append(obs+'/'+key)
        if r['method'] == 'J' and not true_value(r['selected_candidate_converged']) and r['joint_optimizer_status'] == 'SUCCESS':
            failures.append(obs+'/false_SUCCESS')
    return failures


if __name__ == '__main__':
    import sys
    from pathlib import Path
    from frozen_pilot import read, sha, ROOT, BASE
    out = Path(sys.argv[1])
    rows = csvread(out/'ab_metrics.csv')
    result = dict(failures=audit_rows(rows, 2.7397868561278864), rows=len(rows))
    artifact = read(out/'artifact_manifest.json')
    result['artifact_hash_mismatches'] = [p for p,h in artifact.items() if not (out/p).is_file() or sha(out/p)!=h]
    frozen = read(out/'input_manifest.json')
    result['input_hash_mismatches'] = [p for p,h in frozen.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h['sha256']]
    source = read(out/'source_manifest.json')
    result['source_hash_mismatches'] = [p for p,h in source.items() if sha(ROOT/p)!=h['sha256'] or sha(out/h['snapshot'])!=h['sha256']]
    a = [r for r in rows if r['budget_group']=='A']
    regress = regression(a,csvread(BASE/'metrics.csv'))
    result['A_history_regression'] = len(regress)==144 and all(r['passed'] for r in regress)
    pairs, controls = paired(rows)
    result['OF_invariant'] = len(controls)==96 and all(r['passed'] for r in controls)
    summary = aggregate(rows)
    saved = csvread(out/'summary_metrics.csv')
    result['summary_recomputed'] = len(summary)==len(saved) and all(
        all(close(r[k],s[k]) for k in r if isinstance(r[k],(int,float))) for r,s in zip(summary,saved))
    gate = gates(rows,result['A_history_regression'],True,not result['input_hash_mismatches'],controls)
    stored = read(out/'pilot_gate.json')
    result['gates_recomputed'] = all(gate[k]['passed']==stored[k]['passed'] for k in ['H0','H1','H2','H3','H4','H5','H6'])
    result['passed'] = (not result['failures'] and len(rows)==288 and not result['artifact_hash_mismatches']
                        and not result['input_hash_mismatches'] and not result['source_hash_mismatches']
                        and result['A_history_regression'] and result['OF_invariant']
                        and result['summary_recomputed'] and result['gates_recomputed'])
    print(json.dumps(result, ensure_ascii=False))
