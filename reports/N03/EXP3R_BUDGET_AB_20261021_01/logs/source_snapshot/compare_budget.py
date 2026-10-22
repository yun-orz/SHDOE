"""受控执行A55/B150；只创建新目录，失败后封存证据且没有full入口。"""
import argparse
import ast
import copy
import difflib
import inspect
import itertools
import json
import os
import platform
import shutil
import sys
import time
import traceback
from datetime import datetime
from types import SimpleNamespace
import numpy as np
import scipy
from scipy.optimize import minimize as scipy_minimize
from frozen_pilot import (ROOT, BASE, CODE, NOTICE, ForwardAdapter, f, noise,
                          read, write, text, sha, array_sha, csvread, csvwrite,
                          gitstate, verify_baseline, prepare)
import validate_results as validation

HISTORICAL_SOLVER = BASE/'logs/source_snapshot/position_solver.py'


def algorithm_ast(maxfev):
    tree = ast.parse(HISTORICAL_SOLVER.read_text(encoding='utf-8-sig'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'joint_solve')
    function = copy.deepcopy(function)
    replacements = 0
    for node in ast.walk(function):
        if isinstance(node, ast.keyword) and node.arg == 'maxfev':
            if not isinstance(node.value, ast.Constant) or node.value.value != 55:
                raise RuntimeError('STOP_CONTRACT_DEVIATION: unexpected maxfev AST')
            node.value = ast.copy_location(ast.Constant(value=maxfev), node.value)
            replacements += 1
    if replacements != 1:
        raise RuntimeError('STOP_CONTRACT_DEVIATION: maxfev replacement count')
    return ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))


def joint_solve(y, model, frozen_params):
    """真值隔离入口；仅允许y、固定matrix接口和预注册参数。"""
    budget = frozen_params['maxfev_per_start']
    if set(frozen_params) != {'maxfev_per_start'} or budget not in (55, 150):
        raise RuntimeError('STOP_CONTRACT_DEVIATION: optimizer parameters')
    current = {'start_id': -1, 'position': None}
    evaluations, endings, requests = [], [], []
    class MatrixOnly:
        __slots__ = ()
        def matrix(self, position):
            current['position'] = tuple(float(v) for v in position)
            begin = time.perf_counter()
            result = model.matrix(position)
            current['matrix_seconds'] = time.perf_counter()-begin
            return result
    def operator_factory(a):
        begin = time.perf_counter()
        operator = f.Operator(a)
        factor_seconds = time.perf_counter()-begin
        class Solving:
            def solve(self, observed):
                if observed is not y:
                    raise RuntimeError('STOP_CONTRACT_DEVIATION: observation identity')
                begin = time.perf_counter()
                result = operator.solve(observed)
                elapsed = time.perf_counter()-begin
                estimate, residual, kkt = result
                evaluations.append(dict(position=list(current['position']),
                                        owner_start_id=current['start_id'],
                                        matrix_seconds=current['matrix_seconds'],
                                        factor_seconds=factor_seconds, nnls_seconds=elapsed,
                                        nnls_success=True, nnls_KKT=kkt,
                                        nnls_nonnegative=bool(np.min(estimate) >= 0),
                                        relative_squared_residual=residual**2))
                return result
        return Solving()
    def recorded_minimize(fun, start, method, bounds, options):
        sid = len(endings)
        current['start_id'] = sid
        expected = dict(maxfev=budget, xtol=1e-5, ftol=1e-10)
        if method != 'Powell' or bounds != [(-.5, .5)]*2 or options != expected:
            raise RuntimeError('STOP_CONTRACT_DEVIATION: scipy options')
        begin = time.perf_counter()
        def observed_fun(p):
            request_start = time.perf_counter()
            before = len(evaluations)
            value = fun(p)
            requests.append(dict(start_id=sid, position=np.asarray(p).tolist(),
                                 cache_hit=len(evaluations) == before,
                                 seconds=time.perf_counter()-request_start))
            return value
        opt = scipy_minimize(observed_fun, start, method=method, bounds=bounds, options=options)
        endings.append(dict(start_id=sid, start=list(start), position=opt.x.tolist(),
                            loss=float(opt.fun), success=bool(opt.success), status=int(opt.status),
                            message=str(opt.message), nfev=int(opt.nfev), nit=int(opt.nit),
                            budget_exhausted=bool(not opt.success and (opt.status == 1 or opt.nfev >= budget)),
                            seconds=time.perf_counter()-begin, maxfev=budget))
        return opt
    algorithm = dict(grid=[-.5, 0., .5], starts=2, local='Powell',
                     maxfev_per_start=budget, max_evaluations=9+2*budget, xtol=1e-5, ftol=1e-10)
    namespace = dict(np=np, itertools=itertools, f=SimpleNamespace(Operator=operator_factory),
                     minimize=recorded_minimize, ALGORITHM=algorithm)
    exec(compile(algorithm_ast(budget), str(HISTORICAL_SOLVER), 'exec'), namespace)
    begin = time.perf_counter()
    result = namespace['joint_solve'](y, MatrixOnly())
    elapsed = time.perf_counter()-begin
    selected = tuple(result['position'])
    # 保守认证：缓存最低点必须逐位等于成功局部优化器的返回终点。
    endpoints = [e for e in endings if tuple(e['position']) == selected]
    certified = [e for e in endpoints if e['success']]
    source = next(e for e in evaluations if tuple(e['position']) == selected)
    selected_id = certified[0]['start_id'] if certified else endpoints[0]['start_id'] if endpoints else source['owner_start_id']
    owner = next((e for e in endings if e['start_id'] == selected_id), None)
    accepted = bool(certified and np.isfinite(result['estimate']).all() and
                    result['estimate'].min() >= 0 and result['kkt'] <= 1e-7)
    status = 'SUCCESS' if accepted else 'NUMERICALLY_INCOMPLETE' if all(e['budget_exhausted'] for e in endings) else 'INCOMPLETE_OPTIMIZATION'
    result.update(seconds=elapsed, selected_start_id=selected_id,
                  selected_candidate_converged=bool(certified),
                  selected_candidate_budget_exhausted=bool(owner and owner['budget_exhausted']),
                  selected_is_returned_endpoint=bool(endpoints),
                  selected_from_converged_run=bool(owner and owner['success']),
                  joint_has_candidate=True, joint_numerically_accepted=accepted,
                  joint_optimizer_status=status,
                  nnls_seconds_total=sum(e['nnls_seconds'] for e in evaluations),
                  factor_seconds_total=sum(e['factor_seconds'] for e in evaluations),
                  matrix_seconds_total=sum(e['matrix_seconds'] for e in evaluations))
    result['trace'].update(terminations=endings, evaluation_records=evaluations,
                           local_requests=requests, selected_start_id=selected_id,
                           selected_candidate_converged=bool(certified),
                           selected_is_returned_endpoint=bool(endpoints),
                           selected_endpoint_distances=[float(np.linalg.norm(np.array(e['position'])-selected)) for e in endings])
    return result


def score(case, group, method, position, estimate, residual, kkt, seconds, joint):
    source = case['source']
    quality = f.SOLVERS.spectral_metrics(case['truth'], estimate, f.WAVES)
    ep = float(np.linalg.norm(np.array(position)-case['position']))
    is_joint = method == 'J'
    return dict(budget_group=group, maxfev_per_start=55 if group == 'A' else 150,
                observation=case['id'], protocol=source['protocol'], seed=int(source['seed']),
                spectrum=source['spectrum'], spectrum_index=int(source['spectrum_index']),
                kind=source['kind'], position_id=int(source['position_id']), method=method,
                dx_true=case['position'][0], dy_true=case['position'][1],
                dx_hat=position[0], dy_hat=position[1], position_error_pixel=ep,
                position_error_um=ep*2.7397868561278864, position_error_nm=ep*2.7397868561278864*1000,
                NRMSE=quality['spectral_NRMSE'], SAM_deg=quality['SAM_deg'],
                energy_bias=quality['relative_amplitude_bias'], relative_residual=residual,
                kkt=kkt, nnls_KKT=kkt, nnls_success=True,
                nnls_nonnegative=bool(estimate.min() >= 0), y_norm=float(np.linalg.norm(case['y'])),
                recovered_energy=float(estimate.sum()), actual_SNR_db=case['snr'],
                truth=json.dumps(case['truth'].tolist()), estimate=json.dumps(estimate.tolist()),
                capture=json.dumps(case['capture'].tolist()), noise_sha256=case['noise_sha256'],
                y_sha256=case['y_sha256'], observation_readonly=not case['y'].flags.writeable,
                evaluations=joint['trace']['evaluations'] if is_joint else 1,
                nnls_calls=joint['trace']['nnls_calls'] if is_joint else 1,
                cache_hits=joint['trace']['cache_hits'] if is_joint else 0,
                requests=joint['trace']['requests'] if is_joint else 1, seconds=seconds,
                matrix_seconds_total=joint['matrix_seconds_total'] if is_joint else 0,
                factor_seconds_total=joint['factor_seconds_total'] if is_joint else 0,
                nnls_seconds_total=joint['nnls_seconds_total'] if is_joint else seconds,
                selected_start_id=joint['selected_start_id'] if is_joint else '',
                selected_candidate_converged=joint['selected_candidate_converged'] if is_joint else '',
                selected_candidate_budget_exhausted=joint['selected_candidate_budget_exhausted'] if is_joint else '',
                selected_is_returned_endpoint=joint['selected_is_returned_endpoint'] if is_joint else '',
                joint_has_candidate=joint['joint_has_candidate'] if is_joint else '',
                joint_numerically_accepted=joint['joint_numerically_accepted'] if is_joint else '',
                joint_optimizer_status=joint['joint_optimizer_status'] if is_joint else 'NOT_APPLICABLE',
                powell_success_each_start=json.dumps([e['success'] for e in joint['trace']['terminations']]) if is_joint else '[]',
                powell_nfev_each_start=json.dumps([e['nfev'] for e in joint['trace']['terminations']]) if is_joint else '[]',
                powell_message_each_start=json.dumps([e['message'] for e in joint['trace']['terminations']]) if is_joint else '[]',
                position_boundary_hit=bool(max(abs(np.array(position))) >= .5-1e-5))


def run_group(out, group, cases, model, rows, traces, terminations):
    start = time.perf_counter()
    for i, case in enumerate(cases):
        if array_sha(case['y']) != case['y_sha256'] or case['y'].flags.writeable:
            raise RuntimeError('STOP_DATA_REPRO: shared observation changed')
        # 顺序保持历史J→O→F，但每个方法单独计时。
        joint = joint_solve(case['y'], model, {'maxfev_per_start':55 if group == 'A' else 150})
        traces[group+'/'+case['id']] = joint['trace']
        for ending in joint['trace']['terminations']:
            terminations.append(dict(budget_group=group, observation=case['id'], **ending))
        solved = []
        for method, operator, p in [('O', case['oracle'], case['position']), ('F', case['fixed'], [0,0])]:
            begin = time.perf_counter()
            estimate, residual, kkt = operator.solve(case['y'])
            solved.append((method, p, estimate, residual, kkt, time.perf_counter()-begin))
        solved.append(('J', joint['position'], joint['estimate'], np.sqrt(joint['loss']), joint['kkt'], joint['seconds']))
        # Oracle只在Joint完成之后做后验评分，不回流初始化或停止判断。
        for method, p, estimate, residual, kkt, seconds in solved:
            row = score(case, group, method, p, estimate, residual, kkt, seconds, joint)
            row.update(objective_joint=joint['loss'], objective_oracle_diagnostic=solved[0][3]**2,
                       objective_fixed=solved[1][3]**2)
            rows.append(row)
        if not np.isclose(joint['loss'], f.Operator(model.matrix(joint['position'])[0]).solve(case['y'])[1]**2,
                          rtol=1e-12, atol=1e-18):
            raise RuntimeError('STOP_CONTRACT_DEVIATION: direct objective differs')
        joint['trace']['posterior_direct_check_nnls_calls'] = 1
        if (i+1) % 6 == 0:
            event(out, 'GROUP_PROGRESS', group=group, observations=i+1,
                  seconds=time.perf_counter()-start)
    return time.perf_counter()-start


def compare_traces(current, historical):
    checks = []
    for obs, old in historical.items():
        new = current['A/'+obs]
        errors = []
        for key in ['evaluations', 'nnls_calls', 'cache_hits', 'requests']:
            if new[key] != old[key]:
                errors.append(key)
        if len(new['candidates']) != len(old['candidates']):
            errors.append('candidate_count')
        else:
            for a, b in zip(new['candidates'], old['candidates']):
                if not np.allclose(a['position'], b['position'], rtol=1e-10, atol=1e-12) or not validation.close(a['relative_squared_residual'], b['relative_squared_residual']):
                    errors.append('candidate_path')
                    break
        for a, b in zip(new['terminations'], old['terminations']):
            if a['success'] != b['success'] or a['nfev'] != b['nfev'] or a['message'] != b['message']:
                errors.append('termination')
        checks.append(dict(observation=obs, passed=not errors, errors=errors))
    return checks


def event(out, stage, **detail):
    entry = dict(time=datetime.now().astimezone().isoformat(), stage=stage, **detail)
    with (out/'logs/events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False)+'\n')
    print(json.dumps(entry, ensure_ascii=False), flush=True)


def plots(out, rows, terminations, cases, model, traces, diagnostic_ids):
    os.environ['MPLCONFIGDIR'] = str(out/'logs/matplotlib_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    jrows = [r for r in rows if r['method'] == 'J']
    index = {(r['budget_group'], r['observation']):r for r in jrows}
    ids = [c['id'] for c in cases]
    def save(fig, filename):
        fig.suptitle(NOTICE, fontsize=8)
        fig.tight_layout(rect=(0,0,1,.93))
        fig.savefig(out/'figures'/filename, dpi=160)
        plt.close(fig)
    fig, axs = plt.subplots(1,2,figsize=(11,4))
    for ax, protocol, threshold in zip(axs,['noiseless','Q40'],[.005,.02]):
        selected = [c['id'] for c in cases if c['source']['protocol'] == protocol]
        for group in ['A','B']:
            ax.plot([index[(group,k)]['position_error_pixel'] for k in selected], '.-', label=group)
        ax.axhline(threshold, color='red', ls='--', label='frozen threshold')
        ax.set(xlabel='Frozen case order', ylabel='Position error (detector pixel)', title=protocol)
        ax.legend()
    save(fig,'position_error_A_vs_B.png')
    fig, ax = plt.subplots(figsize=(8,4))
    labels, counts = [], []
    for group in ['A','B']:
        es = [e for e in terminations if e['budget_group'] == group]
        for key in ['success','budget_exhausted']:
            labels.append(group+'/'+key); counts.append(sum(e[key] for e in es))
    ax.bar(labels, counts); ax.set(ylabel='Local starts', title='All starts, including failures')
    save(fig,'optimizer_convergence_budget.png')
    fig, axs = plt.subplots(1,2,figsize=(10,4))
    for ax, protocol in zip(axs,['noiseless','Q40']):
        selected = [c['id'] for c in cases if c['source']['protocol'] == protocol]
        for group in ['A','B']:
            ax.semilogy([max(index[(group,k)]['NRMSE'],1e-16) for k in selected],'.-',label=group)
        ax.set(xlabel='Frozen case order',ylabel='Spectral NRMSE',title=protocol);ax.legend()
    save(fig,'paired_spectral_NRMSE.png')
    fig, axs = plt.subplots(2,2,figsize=(11,9))
    maps = []
    for ax, obs in zip(axs.flat, diagnostic_ids):
        case = next(c for c in cases if c['id'] == obs)
        center = np.array(case['position'])
        xs = np.linspace(center[0]-.08,center[0]+.08,9)
        ys = np.linspace(center[1]-.08,center[1]+.08,9)
        z = np.array([[f.Operator(model.matrix((x,y))[0]).solve(case['y'])[1]**2 for x in xs] for y in ys])
        im = ax.pcolormesh(xs,ys,np.log10(np.maximum(z,1e-30)),shading='nearest')
        fig.colorbar(im,ax=ax,label='log10 relative squared residual')
        ax.plot(*center,'w+',ms=9,label='GT posterior')
        for group,color in [('A','red'),('B','cyan')]:
            r = index[(group,obs)]
            ax.plot(r['dx_hat'],r['dy_hat'],'x',color=color,label=group+' estimate')
            for ending in traces[group+'/'+obs]['terminations']:
                ax.plot(*ending['start'],marker='o',mfc='none',color=color,ms=5)
        # 全部初值以数值注释显示，避免把局部网格扩为全域造成误读。
        starts = [e['start'] for e in traces['A/'+obs]['terminations']]
        ax.text(.01,.01,'Initial starts: '+str(starts),transform=ax.transAxes,fontsize=7)
        ax.set(xlim=(xs[0],xs[-1]),ylim=(ys[0],ys[-1]),xlabel='dx (pixel)',ylabel='dy (pixel)',title=obs)
        ax.legend(fontsize=7)
        maps.append(dict(observation=obs,x=xs.tolist(),y=ys.tolist(),relative_squared_residual=z.tolist(),
                         evaluations=81, posterior_only=True, fed_to_optimizer=False, initial_starts=starts))
    save(fig,'worst_cases_position_objective.png')
    write(out/'objective_maps.json',dict(notice=NOTICE,total_evaluations=324,maps=maps,
                                       scope='固定局部9x9；不认证全域唯一性；不产生救援估计'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=__import__('pathlib').Path, required=True)
    parser.add_argument('--task', type=__import__('pathlib').Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.parent != ROOT/'reports/N03' or not out.name.startswith('EXP3R_BUDGET_AB_'):
        raise ValueError('仅允许新EXP3R目录')
    out.mkdir(exist_ok=False)
    for folder in ['logs','figures','logs/source_snapshot']:
        (out/folder).mkdir(exist_ok=False)
    begin = time.perf_counter()
    before = gitstate()
    rows, traces, terminations, checks = [], {}, [], []
    frozen = {}
    decision = None
    error = None
    timing = {}
    try:
        # 纳入所有既有研究资产和报告；缓存及Git内部文件不属于科研输入。
        protected = [p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and
                     '__pycache__' not in p.parts and 'runtime_cache' not in p.parts and
                     out not in p.parents and CODE not in p.parents and p.name != 'test_n03_exp3r.py']
        frozen = {str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in protected}
        write(out/'input_manifest.json',frozen)
        event(out,'INPUTS_FROZEN',files=len(frozen))
        baseline = verify_baseline()
        config = read(BASE/'run_config.json')
        model = ForwardAdapter()
        historical = csvread(BASE/'metrics.csv')
        if (platform.python_version()!=config['environment']['python'].split()[0] or
                np.__version__!=config['environment']['numpy'] or scipy.__version__!=config['environment']['scipy']):
            raise RuntimeError('STOP_CONTRACT_DEVIATION: environment versions')
        if any(os.environ.get(k) != '4' for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']):
            raise RuntimeError('STOP_CONTRACT_DEVIATION: four-thread environment')
        gates = read(ROOT/'optics/n02_single_spiral/results/n02/n02_20261019_02/gates.json')
        if read(ROOT/'reports/N03/00_manifest.json')['decision']!='G0_FAIL_STOP' or any(gates[k]['status']!='FAIL' for k in ['G2','G3_Numerics']):
            raise RuntimeError('STOP_CONTRACT_DEVIATION: upstream gate')
        cases, observations = prepare(model,config,historical)
        write(out/'observations_manifest.json',dict(notice=NOTICE,observations=observations,
                                                    source='冻结旧前向与种子重建；旧包未存完整y字节',
                                                    AB_same_memory_object=True,P_protocol='NOT_RUN',Q40_seeds=[20261021]))
        diagnostic_ids = ['pilot_4_9_0','pilot_3_9_0','pilot_4_13_0','pilot_0_0_0']
        contract = dict(notice=NOTICE,baseline=str(BASE),baseline_hash_verification=baseline,
                        task=dict(path=str(args.task),sha256=sha(args.task)),git_before=before,
                        environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,
                                         executable=sys.executable,threads=4,device='CPU'),
                        cases=observations,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in CODE.glob('*.py')},
                        A=dict(maxfev_per_start=55),B=dict(maxfev_per_start=150),
                        timing_policy='J包含候选matrix/SVD/NNLS；O/F分别计时solve；O/F算子在冻结输入阶段共享预构造，不将共享setup冒充两次实测耗时。每例另有1次后验直接NNLS校验，不计入搜索调用。',
                        unchanged_parameters=dict(grid=[-.5,0,.5],starts=2,method='Powell',bounds=[[-.5,.5]]*2,
                                                  xtol=1e-5,ftol=1e-10,selection='按原缓存插入顺序稳定排序，取最低实测相对平方残差',
                                                  objective='(norm(A(p)@NNLS(A(p),y)-y)/max(norm(y),1e-300))**2'),
                        historical_regression_tolerances=validation.TOLERANCE,
                        selected_convergence_definition='选中缓存坐标与success=True的Powell返回终点逐位相同；仅属于成功运行的中间评价点不算认证',
                        theoretical_unique_evaluation_caps=dict(A=119,B=309),
                        thresholds=dict(clean_position_max=.005,Q40_position_max=.02,NRMSE=.01,spectral_fraction=.8,KKT=1e-7),
                        diagnostic_maps=dict(ids=diagnostic_ids,grid=9,half_width_px=.08,evaluations=324,posterior_only=True),
                        full='NOT_RUN 0/504;本运行器没有full分支',failure_policy='A回归不通过不运行B；B48例仅运行一次，未达门停止',
                        frozen_input_manifest_sha256=sha(out/'input_manifest.json'))
        write(out/'frozen_contract.json',contract)
        text(out/'00_preflight.md',NOTICE+'\n\n已冻结'+str(len(frozen))+'个既有文件；旧输入与最终包哈希通过。48个case的噪声哈希一致，观测只读且A/B共享同一对象。\n\n'+
             '唯一干预：Powell每起点maxfev55→150。完整源/输入哈希、case与门限见frozen_contract和input_manifest。A完整回归前不运行B。full固定NOT_RUN。\n')
        a_source = ast.unparse(algorithm_ast(55))
        b_source = ast.unparse(algorithm_ast(150))
        diff = ''.join(difflib.unified_diff(a_source.splitlines(True),b_source.splitlines(True),fromfile='A55',tofile='B150'))
        text(out/'diff_A_vs_B.md',NOTICE+'\n\n直接编译canonical旧joint_solve函数AST，只修改唯一maxfev常量；断言上限随预算派生，不参与数值优化。记录通过代理包装matrix/NNLS/minimize，不改变返回值和候选顺序。\n\n```diff\n'+diff+'\n```\n')
        # 测试用mock优化器，不额外运行物理定位实验。
        test_path = CODE.parent/'tests/test_n03_exp3r.py'
        spec = __import__('importlib.util',fromlist=['spec_from_file_location']).spec_from_file_location('exp3r_tests',test_path)
        test = __import__('importlib.util',fromlist=['module_from_spec']).module_from_spec(spec)
        spec.loader.exec_module(test)
        checks.extend(test.checks(sys.modules[__name__],cases,model))
        write(out/'preflight_tests.json',checks)
        if not all(t['passed'] for t in checks):
            raise RuntimeError('STOP_CONTRACT_DEVIATION: preflight tests')
        event(out,'R0_PASS',observations=48,noise_fingerprints=48)
        timing['A_seconds'] = run_group(out,'A',cases,model,rows,traces,terminations)
        regress = validation.regression(rows,historical)
        csvwrite(out/'archived_A_regression.csv',regress)
        path_checks = compare_traces(traces,read(BASE/'optimization_traces.json'))
        write(out/'archived_A_trace_regression.json',path_checks)
        h0 = all(r['passed'] for r in regress) and len(regress)==144 and all(r['passed'] for r in path_checks)
        checks.append(dict(name='A144行与历史全部轨迹回归',passed=h0,rows=len(regress)))
        if not h0:
            raise RuntimeError('STOP_DATA_REPRO: A historical regression')
        event(out,'A_HISTORY_REGRESSION_PASS',rows=144,traces=48)
        timing['B_seconds'] = run_group(out,'B',cases,model,rows,traces,terminations)
        csvwrite(out/'ab_metrics.csv',rows)
        # 重新读CSV验证，保证发布数据而非内存摘要可独立还原。
        csvrows = csvread(out/'ab_metrics.csv')
        audit_failures = validation.audit_rows(csvrows,model.pitch)
        checks.append(dict(name='独立CSV逐行指标和状态回算',passed=not audit_failures,failures=audit_failures))
        pairs, controls = validation.paired(rows)
        csvwrite(out/'paired_improvement.csv',pairs)
        csvwrite(out/'OF_invariance.csv',controls)
        summaries = validation.aggregate(csvrows)
        csvwrite(out/'summary_metrics.csv',summaries)
        selected = [p for p in pairs if p['observation'] in diagnostic_ids[:3] or
                    p['observation'].replace('_20261021','_0') in diagnostic_ids[:3]]
        csvwrite(out/'historical_worst_case_pairs.csv',selected)
        checks.append(dict(name='O/F两预算逐例完全不变',passed=len(controls)==96 and all(r['passed'] for r in controls)))
        unchanged = [name for name,entry in frozen.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=entry['sha256']]
        integrity = not unchanged and gitstate()['tracked_diff_sha256']==before['tracked_diff_sha256'] and gitstate()['head']==before['head']
        checks.append(dict(name='全部冻结既有文件与tracked差异保留',passed=integrity,changed=unchanged))
        decision = validation.gates(rows,h0,all(t['passed'] for t in checks),integrity,controls)
        event(out,'PILOT_GATES',decision=decision['decision'],H2=decision['H2'],H3=decision['H3'],H5=decision['H5'])
        plots(out,rows,terminations,cases,model,traces,diagnostic_ids)
    except Exception as exc:
        error = traceback.format_exc()
        text(out/'logs/failure_record.md',NOTICE+'\n\n```text\n'+error+'\n```\n')
        message = str(exc)
        status = next((s for s in ['STOP_DATA_REPRO','STOP_CONTRACT_DEVIATION'] if s in message),'PARTIAL')
        if decision is None:
            decision = {k:dict(passed=False,status='NOT_RUN_OR_STOPPED') for k in ['H0','H1','H2','H3','H4','H5','H6']}
            decision.update(decision=status,full=dict(status='NOT_RUN',observations=0,planned=504),error=message,
                            upstream={'N03_G0':'FAIL','N02_G2':'FAIL','N02_G3_Numerics':'FAIL'})
        else:
            decision['decision'] = 'PARTIAL'
            decision['H6'].update(passed=False, error=message)
        event(out,'STOPPED',reason=message)
    finally:
        # 最终封存允许写新产物，绝不覆盖任何已有文件。
        if not (out/'ab_metrics.csv').exists(): csvwrite(out/'ab_metrics.csv',rows)
        csvwrite(out/'optimizer_terminations.csv',terminations)
        write(out/'optimization_traces.json',traces)
        write(out/'tests.json',checks)
        changed = [name for name,entry in frozen.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=entry['sha256']]
        after = gitstate()
        source_manifest = {}
        for path in list(CODE.glob('*.py'))+[CODE.parent/'tests/test_n03_exp3r.py']:
            if path.is_file():
                target = out/'logs/source_snapshot'/path.name
                shutil.copyfile(path,target)
                source_manifest[str(path.relative_to(ROOT))] = dict(sha256=sha(path),snapshot=str(target.relative_to(out)))
        write(out/'source_manifest.json',source_manifest)
        post = dict(inputs_unchanged=not changed,changed=changed,head_unchanged=after['head']==before['head'],
                    tracked_diff_unchanged=after['tracked_diff_sha256']==before['tracked_diff_sha256'],
                    git_before=before,git_after=after,full_observations=0,upstream_gates_unchanged=True)
        write(out/'postrun_checks.json',post)
        if changed or not post['head_unchanged'] or not post['tracked_diff_unchanged']:
            decision['decision']='FAIL_INTEGRITY'
            decision['H6'].update(passed=False,changed=changed)
        write(out/'pilot_gate.json',decision)
        summaries = validation.aggregate(rows) if rows else []
        compact = [r for r in summaries if r['dimension']=='ALL' and r['method']=='J']
        statistics = {}
        for group in ['A','B']:
            es=[e for e in terminations if e['budget_group']==group]
            js=[r for r in rows if r['budget_group']==group and r['method']=='J']
            statistics[group]=dict(observations=len(js),local_starts=len(es),converged_starts=sum(e['success'] for e in es),
                                   budget_exhausted_starts=sum(e['budget_exhausted'] for e in es),
                                   selected_converged=sum(r['selected_candidate_converged'] for r in js),
                                   maximum_unique_evaluations=max([r['evaluations'] for r in js],default=0))
        write(out/'result_statistics.json',dict(notice=NOTICE,timing=timing,optimizer=statistics,Joint=compact))
        header = NOTICE+'\n\n'+decision['decision']+'；full NOT_RUN（0/504）。\n\n'
        header += 'A/B各目标48观测；实际 '+str({g:statistics[g]['observations'] for g in ['A','B']})+'。\n\n'
        header += 'H0–H6：'+json.dumps({k:decision[k] for k in ['H0','H1','H2','H3','H4','H5','H6']},ensure_ascii=False)+'\n\n'
        for r in compact:
            header += f"{r['budget_group']} {r['protocol']}: position mean/median/P90/max={r['position_error_pixel_mean']:.12g}/{r['position_error_pixel_median']:.12g}/{r['position_error_pixel_p90']:.12g}/{r['position_error_pixel_max']:.12g} px；NRMSE median/max={r['NRMSE_median']:.12g}/{r['NRMSE_max']:.12g}。\n\n"
        header += '优化器：'+json.dumps(statistics,ensure_ascii=False)+'\n\n'
        header += 'A/B共享只读观测，noise/y指纹见 observations_manifest.json；A历史逐例和轨迹回归见 archived_A_regression.csv / archived_A_trace_regression.json。\n\n'
        header += '原始288行（完整执行时）、配对统计与全部局部终止分别见 ab_metrics.csv、paired_improvement.csv、optimizer_terminations.csv；代码快照在 logs/source_snapshot；最终SHA256在artifact_manifest.json。\n\n'
        header += 'N03 G0 FAIL；N02 G2/G3_Numerics FAIL。单seed Q40，无P预算；同模型shape_only合成恢复，不认证物理精度。局部图后验计算且没有回流Joint，不证明全局唯一性。没有追加B重试、full或参数扫描。等待ChatGPT经Bridge只读审核。\n'
        if error: header+='\n停止异常详见logs/failure_record.md。\n'
        text(out/'result_summary.md',header)
        text(out/'DELIVERY.md',header)
        write(out/'logs/run_record.json',dict(status=decision['decision'],seconds=time.perf_counter()-begin,
                                             timing=timing,observations=statistics,rows=len(rows),
                                             argv=sys.argv,git_before=before,git_after=after))
        text(out/'logs/run_commands.md','本次实际命令：\n\n'+subprocess_command()+'\n\n验证器只读：python -B integration/single_spiral_to_hsi/n03_exp3r/validate_results.py <本目录>\n')
        write(out/'artifact_manifest.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
        print(json.dumps(dict(delivery=str(out/'DELIVERY.md'),status=decision['decision'],rows=len(rows)),ensure_ascii=False),flush=True)


def subprocess_command():
    import subprocess
    return subprocess.list2cmdline([sys.executable,'-B',*sys.argv])


if __name__ == '__main__':
    main()
