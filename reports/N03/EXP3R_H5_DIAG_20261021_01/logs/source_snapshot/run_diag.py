"""D0→D1→D2→条件D3；旧门只读，所有写入限定新报告目录。"""
import argparse
import ast
import copy
import csv
import hashlib
import inspect
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
import numpy as np
import scipy
import diagnostics as core
from io_contract import ROOT,CODE,BASE,EXP3,NOTICE,read,csvread,sha,gitstate,OutputWriter


def truth_value(v):return v is True or v=='True'


def event(writer,stage,**details):
    row=dict(time=datetime.now().astimezone().isoformat(),stage=stage,**details)
    with writer.path('logs/events.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps(row,ensure_ascii=False),flush=True)


def check_hash_map(directory,manifest):
    bad=[]
    for name,value in read(manifest).items():
        digest=value['sha256'] if isinstance(value,dict) else value
        p=directory/name
        if not p.is_file() or sha(p)!=digest:bad.append(name)
    return bad


def phase0(writer,task,frozen,before):
    required=['FINAL_INDEX.md','DELIVERY.md','result_summary.md','status_semantics.md','frozen_contract.json',
              'pilot_gate.json','final_qa.json','ab_metrics.csv','optimizer_terminations.csv',
              'selection_provenance.csv','paired_improvement.csv','archived_A_regression.csv',
              'input_manifest.json','source_manifest.json','final_delivery_manifest.json','optimization_traces.json',
              'observations_manifest.json']
    missing=[str(BASE/name) for name in required if not (BASE/name).is_file()]
    if missing:raise RuntimeError('UNVERIFIED: missing inputs '+repr(missing))
    bad=check_hash_map(BASE,BASE/'final_delivery_manifest.json')+check_hash_map(ROOT,BASE/'input_manifest.json')
    for name,entry in read(BASE/'source_manifest.json').items():
        if sha(ROOT/name)!=entry['sha256'] or sha(BASE/entry['snapshot'])!=entry['sha256']:bad.append(name)
    if bad:raise RuntimeError('UNVERIFIED: old hashes '+repr(bad))
    original=read(BASE/'pilot_gate.json')
    if not (original['decision']=='EXP3R_PILOT_FAIL' and original['H5']['passed'] is False and
            all(original[k]['passed'] for k in ['H2','H3','H4']) and original['full']['observations']==0):
        raise RuntimeError('UNVERIFIED: original gates conflict')
    upstream=read(ROOT/'optics/n02_single_spiral/results/n02/n02_20261019_02/gates.json')
    if read(ROOT/'reports/N03/00_manifest.json')['decision']!='G0_FAIL_STOP' or any(upstream[k]['status']!='FAIL' for k in ['G2','G3_Numerics']):
        raise RuntimeError('UNVERIFIED: upstream gates conflict')
    oldcfg=read(BASE/'frozen_contract.json')
    rows=csvread(BASE/'ab_metrics.csv')
    grouped={}
    for r in rows:grouped.setdefault(r['observation'],[]).append(r)
    if len(rows)!=288 or len(grouped)!=48 or any(len(g)!=6 or len({r['y_sha256'] for r in g})!=1 or
            len({r['noise_sha256'] for r in g})!=1 for g in grouped.values()):
        raise RuntimeError('UNVERIFIED: same 48 observations')
    sys.path.insert(0,str(ROOT/'integration/single_spiral_to_hsi/n03_exp3r'))
    import compare_budget as previous
    import validate_results as old_validation
    arows=[r for r in rows if r['budget_group']=='A']
    regression=old_validation.regression(arows,csvread(EXP3/'metrics.csv'))
    saved=csvread(BASE/'archived_A_regression.csv')
    if len(regression)!=144 or not all(r['passed'] for r in regression) or not all(truth_value(r['passed']) for r in saved):
        raise RuntimeError('UNVERIFIED: A historical regression')
    a,b=previous.algorithm_ast(55),previous.algorithm_ast(150)
    for node in ast.walk(b):
        if isinstance(node,ast.keyword) and node.arg=='maxfev':node.value.value=55
    if ast.dump(a)!=ast.dump(b) or oldcfg['A']!={'maxfev_per_start':55} or oldcfg['B']!={'maxfev_per_start':150}:
        raise RuntimeError('UNVERIFIED: numerical intervention')
    source=(ROOT/'integration/single_spiral_to_hsi/n03_exp3r/compare_budget.py').read_text(encoding='utf-8')
    source_lines=source.splitlines(keepends=True)
    rule=''.join(source_lines[111:123])
    writer.text('original_H5_verbatim.txt',rule+'\n原冻结定义：\n'+oldcfg['selected_convergence_definition']+'\n\n原gate：\n'+json.dumps(original['H5'],ensure_ascii=False,indent=2))
    provenance=csvread(BASE/'selection_provenance.csv')
    sampling=[]
    classes=[('certified_returned_endpoint',2),('seen_in_converged_start_not_returned_endpoint',3),('seen_only_in_nonconverged_starts',3)]
    for label,count in classes:
        sampling += sorted(r['observation'] for r in provenance if r['budget_group']=='B' and r['category']==label)[:count]
    sampling += [obs for obs in sorted(grouped) if obs not in sampling][:8-len(sampling)]
    assets={name:entry for name,entry in frozen.items() if
            ('n02_20261019_02' in name and ('cases' in name and Path(name).stem in ['420nm','450nm','480nm','510nm','540nm','570nm','600nm','630nm','660nm'] or
                                          'height' in name.lower() or 'mask' in name.lower())) or
            name.endswith('BFS-U3-200S7C-C.json') or
            any(name.endswith(part) for part in ['n03_exp3/forward_adapter.py','n03_exp3\\forward_adapter.py','n03_exp2/forward.py','n03_exp2\\forward.py','n03_exp2/sampling.py','n03_exp2\\sampling.py'])}
    writer.json('asset_hashes.json',assets)
    contract=dict(notice=NOTICE,phase='N03-A-EXP3R-H5-DIAG',created_at=datetime.now().astimezone().isoformat(),
                  canonical=str(BASE),task=dict(path=str(task),sha256=sha(task)),git_before=before,
                  original_gate=original,original_H5_rule_sha256=sha(writer.path('original_H5_verbatim.txt')),
                  original_H5_permanently_preserved=True,derived_budget_guard=dict(A=119,B=309,independent_intervention=False),
                  D1=dict(observations=48,starts=96,classification='精确坐标+local_requests的实际起点来源',
                          exact_equality='tuple(endpoint.position)==tuple(best_position) and endpoint.success'),
                  thresholds=dict(position_near_px=1e-5,machine_near_px=1e-12,float_near_px=1e-8,
                                  objective_abs_near=1e-10,relative_denominator_floor=1e-12,
                                  reevaluation_atol=1e-15,reevaluation_rtol=1e-9,KKT=1e-7),
                  D2=dict(selection='先按归档成功终点loss稳定取最小；无成功终点明确缺失；再重评价和后验评分',
                          no_truth_selection=True,reevaluation_unique_upper_bound=125,
                          per_observation_C0_one_plus_successful_endpoints_at_most_two=True),
                  D3=dict(conditional=True,trigger='D1/D2完整可核验且诊断仍INCONCLUSIVE或40未认证中仍>20例未解释',
                          skip_when_explained=True,selected_ids=sampling,selection_rule='原8/28/12分类分别按ID字典序取2/3/3；不足按全体剩余ID补齐',
                          method='Powell',max_starts=8,maxfev=80,total_evaluation_cap=640,
                          bounds=[[-.5,.5],[-.5,.5]],xtol=1e-5,ftol=1e-10,
                          start='历史B cache-best；只运行一次，无新网格，无替代算法'),
                  decision_rule='语义证据要求来自成功起点的中间点接近对应成功终点，并且C1距离/目标接近；>20/40且有收敛限制证据→MIXED；仅多数语义→SELECTION_SEMANTICS_DOMINANT；仅收敛限制→CONVERGENCE_LIMITED；否则INCONCLUSIVE；见diagnostics.diagnose',
                  source_sha256={str(p.relative_to(ROOT)):sha(p) for p in CODE.glob('*.py')},
                  full='NOT_RUN 0/504;原H5及所有上游FAIL不重判')
    writer.json('diagnostic_contract.json',contract)
    writer.text('diagnostic_contract.sha256',sha(writer.path('diagnostic_contract.json'))+'  diagnostic_contract.json\n')
    writer.text('00_preflight.md',NOTICE+'\n\n本轮不会重判EXP3R的旧H5；历史H5 FAIL永久保留。\n\n'+
                '旧输入、产物、源码/快照SHA全部核对；A144行对旧EXP3离线回归通过；48幅AB y/noise指纹同一。原H2/H3/H4 PASS、H5 FAIL、full 0/504。\n\n'+
                '主要干预仅55→150，派生guard119→309不是独立变量。本轮D1不运行优化，D2只重新评价确定位置；D3仅在冻结条件触发时执行。\n\n'+
                '实际接口、原H5逐字摘录见original_H5_verbatim；资产SHA见asset_hashes；全部旧文件见input_manifest；没有路径替代。\n')
    return rows,contract


def phase1(writer,rows,contract):
    traces=read(BASE/'optimization_traces.json')
    saved={r['observation']:r for r in csvread(BASE/'selection_provenance.csv') if r['budget_group']=='B'}
    b=[r for r in rows if r['budget_group']=='B' and r['method']=='J']
    audit=[];terminations=[];availability=[];mismatches=[]
    category_map={'SUCCESSFUL_RETURN_ENDPOINT':'certified_returned_endpoint',
                  'SUCCESSFUL_START_INTERMEDIATE':'seen_in_converged_start_not_returned_endpoint',
                  'UNSUCCESSFUL_START_ONLY':'seen_only_in_nonconverged_starts'}
    for r in b:
        obs=r['observation'];t=traces.get('B/'+obs,{})
        info=core.classify(t)
        availability.append(dict(observation_id=obs,status=info['status'],missing=info.get('missing',[]),
                                 candidates=len(t.get('candidates',[])),local_requests=len(t.get('local_requests',[])),
                                 evaluation_records=len(t.get('evaluation_records',[])),
                                 all_candidate_spectra_stored=False,endpoint_spectra_stored=False,
                                 reconstruction='D2冻结模型确定位置重评价；不伪称归档已有谱向量'))
        if info['status']!='VERIFIED':continue
        best=t['best_position'];fcache=t['best_loss']
        est=json.loads(r['estimate'])
        finite=all(math.isfinite(x) for x in est)
        nonnegative=min(est)>=0
        kkt=max(e['nnls_KKT'] for e in t['evaluation_records'])
        strict=info['strict'] and finite and nonnegative and float(r['nnls_KKT'])<=1e-7
        replay=(strict==truth_value(r['selected_candidate_converged']) and
                strict==truth_value(saved[obs]['certified_returned_endpoint']) and
                category_map[info['provenance']]==saved[obs]['category'])
        if not replay:mismatches.append(obs+'/H5_or_provenance')
        if not math.isclose(float(r['relative_residual'])**2,fcache,rel_tol=1e-12,abs_tol=1e-18):mismatches.append(obs+'/objective_square')
        if best!=[float(r['dx_hat']),float(r['dy_hat'])]:mismatches.append(obs+'/selected_position')
        candidates=t['candidates']
        bestrecord=min(candidates,key=lambda c:c['relative_squared_residual'])
        if bestrecord['position']!=best or not math.isclose(bestrecord['relative_squared_residual'],fcache,rel_tol=1e-12,abs_tol=1e-18):mismatches.append(obs+'/cache_rank')
        if len(t['evaluation_records'])!=t['nnls_calls'] or len(candidates)!=t['nnls_calls']:mismatches.append(obs+'/call_count')
        near=info['nearest_successful_endpoint_distance']
        entry=dict(observation_id=obs,protocol=r['protocol'],spectrum_id=r['spectrum'],seed=int(r['seed']),
                   position_id=int(r['position_id']),selected_xy_px=json.dumps(best),selected_objective=fcache,
                   selected_start_id=info['selected_start_id'],selected_provenance=info['provenance'],
                   has_successful_endpoint=info['has_successful_endpoint'],strict_same=info['strict'],
                   nearest_successful_endpoint_distance=near,
                   corresponding_successful_endpoint_distance=info['corresponding_successful_endpoint_distance'],
                   float_near_1e8=near is not None and near<=1e-8,
                   within_old_xtol_1e5=near is not None and near<=1e-5,
                   machine_near_1e12=near is not None and near<=1e-12,
                   nnls_call_completed=all(e['nnls_success'] for e in t['evaluation_records']),
                   nnls_KKT_max=kkt,NNLS_KKT_pass=kkt<=1e-7,selected_finite=finite,selected_nonnegative=nonnegative,
                   candidate_finite_source='旧Operator异常guard；轨迹未逐候选保存谱向量',
                   strict_H5_certified=strict,H5_replay_matches=replay,
                   powell_success_each_start=json.dumps([e['success'] for e in t['terminations']]),
                   termination_records=json.dumps(t['terminations']),
                   position_error_px=float(r['position_error_pixel']),NRMSE=float(r['NRMSE']),SAM_deg=float(r['SAM_deg']))
        audit.append(entry)
        for e in t['terminations']:
            delta=e['loss']-fcache
            terminations.append(dict(observation_id=obs,protocol=r['protocol'],**e,
                                     selected_xy_px=json.dumps(best),selected_objective=fcache,
                                     endpoint_distance=core.distance(e['position'],best),
                                     objective_delta=delta,objective_delta_rel=delta/max(abs(fcache),1e-12),
                                     exact_same=tuple(e['position'])==tuple(best)))
    writer.json('trace_availability.json',dict(notice=NOTICE,observations=availability,
                                              archived_source='EXP3R optimization_traces.json',
                                              complete=len(audit)==48,limitations=['无逐候选9维谱；D2需固定位置NNLS重评价','轨迹不认证全域最优']))
    writer.csv('provenance_audit.csv',audit)
    writer.csv('termination_audit.csv',terminations)
    counts=Counter(r['selected_provenance'] for r in audit)
    replay=dict(passed=not mismatches and len(audit)==48 and len(terminations)==96,
                observations=len(audit),starts=len(terminations),counts=dict(counts),
                successful_starts=sum(e['success'] for e in terminations),
                budget_exhausted_starts=sum(e['budget_exhausted'] for e in terminations),
                observations_with_successful_start=sum(r['has_successful_endpoint'] for r in audit),
                strict_H5_count=sum(r['strict_H5_certified'] for r in audit),
                uncertified_float_near=sum(not r['strict_H5_certified'] and r['float_near_1e8'] for r in audit),
                mismatches=mismatches,original_gate=contract['original_gate']['H5'],
                original_decision=contract['original_gate']['decision'],old_H5_preserved=True)
    if replay['strict_H5_count']!=contract['original_gate']['H5']['accepted']:replay['passed']=False
    writer.json('h5_exact_replay.json',replay)
    writer.text('D1_findings.md',NOTICE+'\n\nObserved：'+json.dumps(replay,ensure_ascii=False,indent=2)+
                '\n\n严格相同、浮点距离与目标差分别记录，任何新近似阈值均不回填原H5。真值误差仅为事后评分。\n')
    if not replay['passed']:raise RuntimeError('UNVERIFIED: D1 exact replay failed')
    return b,audit,traces,replay


def evaluate_point(y,model,position,counter):
    """确定位置重评价，只接收观测、模型和坐标，不接收真值。"""
    from frozen_pilot import f
    a,capture=model.matrix(position)
    estimate,residual,kkt=f.Operator(a).solve(y)
    counter['nnls_calls']+=1
    finite=bool(np.isfinite(estimate).all())
    nonnegative=bool(estimate.min()>=0)
    if not finite or not nonnegative or kkt>1e-7:raise RuntimeError('D2 NNLS invalid')
    return dict(position=list(position),objective=float(residual**2),relative_residual=float(residual),
                estimate=estimate.tolist(),KKT=float(kkt),finite=finite,nonnegative=nonnegative)


def score(point,case):
    """选点完成后独立评分；不得供选择函数或微型优化器调用。"""
    from frozen_pilot import f
    estimate=np.array(point['estimate'])
    q=f.SOLVERS.spectral_metrics(case['truth'],estimate,f.WAVES)
    return dict(position_error_px=float(np.linalg.norm(np.array(point['position'])-case['position'])),
                NRMSE=q['spectral_NRMSE'],SAM_deg=q['SAM_deg'])


def phase2(writer,brows,audit,traces,contract):
    from frozen_pilot import ForwardAdapter,prepare,BASE as ignored
    model=ForwardAdapter()
    config=read(EXP3/'run_config.json')
    cases,manifest=prepare(model,config,csvread(EXP3/'metrics.csv'))
    expected={r['observation']:r for r in read(BASE/'observations_manifest.json')['observations']}
    if any(r['y_sha256']!=expected[r['observation']]['y_sha256'] or r['noise_sha256']!=expected[r['observation']]['noise_sha256'] for r in manifest):
        raise RuntimeError('UNVERIFIED: D2 observation fingerprints')
    writer.json('D2_observations_manifest.json',dict(notice=NOTICE,source='冻结旧前向/seed重建，非归档y原始字节',cases=manifest))
    caseindex={c['id']:c for c in cases}
    infoindex={r['observation_id']:r for r in audit}
    comparisons=[];evaluations=[];counter={'nnls_calls':0};failures=[]
    for r in brows:
        obs=r['observation'];case=caseindex[obs];t=traces['B/'+obs]
        # C1先按归档目标排序，再重评价；不因重评价或真值改变选择。
        chosen=core.select_endpoint(t['terminations'])
        cache={}
        for kind,p in [('C0',t['best_position'])]+[(f"endpoint_{e['start_id']}",e['position']) for e in t['terminations'] if e['success']]:
            key=tuple(p)
            if key not in cache:cache[key]=evaluate_point(case['y'],model,p,counter)
            value=cache[key]
            expected_loss=t['best_loss'] if kind=='C0' else next(e['loss'] for e in t['terminations'] if f"endpoint_{e['start_id']}"==kind)
            delta=value['objective']-expected_loss
            okay=math.isclose(value['objective'],expected_loss,rel_tol=contract['thresholds']['reevaluation_rtol'],abs_tol=contract['thresholds']['reevaluation_atol'])
            evaluations.append(dict(observation_id=obs,kind=kind,position=json.dumps(p),
                                    stored_objective=expected_loss,recomputed_objective=value['objective'],
                                    delta=delta,passed=okay,nnls_KKT=value['KKT'],finite=value['finite'],nonnegative=value['nonnegative']))
            if not okay:failures.append(obs+'/'+kind)
        c0=cache[tuple(t['best_position'])];s0=score(c0,case)
        if not np.allclose(c0['estimate'],json.loads(r['estimate']),rtol=1e-10,atol=1e-12):failures.append(obs+'/C0_spectrum')
        row=dict(observation_id=obs,protocol=r['protocol'],spectrum_id=r['spectrum'],seed=int(r['seed']),
                 position_id=int(r['position_id']),provenance=infoindex[obs]['selected_provenance'],
                 corresponding_successful_endpoint_distance=infoindex[obs]['corresponding_successful_endpoint_distance'],
                 strict_H5_certified=infoindex[obs]['strict_H5_certified'],
                 C0_xy=json.dumps(c0['position']),C0_objective=c0['objective'],C0_estimate=json.dumps(c0['estimate']),
                 C0_KKT=c0['KKT'],**{'C0_'+k:v for k,v in s0.items()},
                 C1_status='AVAILABLE' if chosen else 'NO_CONVERGED_ENDPOINT',
                 C1_start_id=chosen['start_id'] if chosen else None)
        if chosen:
            c1=cache[tuple(chosen['position'])];s1=score(c1,case)
            delta=c1['objective']-c0['objective']
            row.update(C1_xy=json.dumps(c1['position']),C1_objective=c1['objective'],
                       C1_estimate=json.dumps(c1['estimate']),C1_KKT=c1['KKT'],
                       **{'C1_'+k:v for k,v in s1.items()},objective_regret=delta,
                       objective_regret_rel=delta/max(abs(c0['objective']),1e-12),
                       position_shift=core.distance(c0['position'],c1['position']),
                       position_error_delta=s1['position_error_px']-s0['position_error_px'],
                       NRMSE_delta=s1['NRMSE']-s0['NRMSE'],SAM_delta=s1['SAM_deg']-s0['SAM_deg'],
                       C1_boundary_hit=max(map(abs,c1['position']))>=.5-1e-5)
        else:
            row.update(C1_xy=None,C1_objective=None,C1_estimate=None,C1_KKT=None,
                       C1_position_error_px=None,C1_NRMSE=None,C1_SAM_deg=None,
                       objective_regret=None,objective_regret_rel=None,position_shift=None,
                       position_error_delta=None,NRMSE_delta=None,SAM_delta=None,C1_boundary_hit=None)
        comparisons.append(row)
    writer.csv('D2_objective_reverification.csv',evaluations)
    writer.csv('endpoint_only_comparison.csv',comparisons)
    if failures or counter['nnls_calls']>125:
        writer.json('D2_decision.json',dict(status='D2_NOT_VERIFIABLE',failures=failures,counts=counter))
        raise RuntimeError('UNVERIFIED: D2 fixed-point objective mismatch')
    summary=[]
    for protocol in ['noiseless','Q40']:
        total=[r for r in comparisons if r['protocol']==protocol]
        for label in ['ALL','SUCCESSFUL_RETURN_ENDPOINT','SUCCESSFUL_START_INTERMEDIATE','UNSUCCESSFUL_START_ONLY']:
            subset=[r for r in total if label=='ALL' or r['provenance']==label]
            valid=[r for r in subset if r['C1_status']=='AVAILABLE']
            entry=dict(protocol=protocol,group=label,total=len(subset),C1_valid=len(valid),
                       no_endpoint=[r['observation_id'] for r in subset if r['C1_status']!='AVAILABLE'])
            for strategy,items in [('C0',subset),('C1',valid)]:
                for metric in ['position_error_px','NRMSE','SAM_deg','objective']:
                    entry[strategy+'_'+metric]=core.stats([r[strategy+'_'+metric] for r in items])
            entry['C1_NRMSE_le_0.01_valid_fraction']=sum(r['C1_NRMSE']<=.01 for r in valid)/len(valid) if valid else None
            entry['C1_NRMSE_le_0.01_all_denominator_fraction']=sum(r['C1_NRMSE']<=.01 for r in valid)/len(subset) if subset else None
            entry['position_shift']=core.stats([r['position_shift'] for r in valid])
            entry['objective_regret']=core.stats([r['objective_regret'] for r in valid])
            entry['C1_position_threshold_exceed_cases']=[r['observation_id'] for r in valid if r['C1_position_error_px']>(.005 if protocol=='noiseless' else .02)]
            summary.append(entry)
    decision=core.diagnose(comparisons,contract['thresholds'])
    decision.update(status='D2_VERIFIED_COUNTERFACTUAL',observations=48,
                    C1_valid=sum(r['C1_status']=='AVAILABLE' for r in comparisons),
                    no_endpoint_cases=[r['observation_id'] for r in comparisons if r['C1_status']!='AVAILABLE'],
                    fixed_point_NNLS_calls=counter['nnls_calls'],new_position_optimization_starts=0,
                    objective_checks=len(evaluations),all_objective_checks_pass=True,
                    old_H5_rejudged=False,summary=summary)
    writer.json('D2_decision.json',decision)
    writer.text('D2_summary.md',NOTICE+'\n\nC1为离线反事实，先按原归档目标选成功返回终点，再使用相同y/模型/NNLS固定坐标重评价。没有新位置优化。\n\n'+
                json.dumps({k:v for k,v in decision.items() if k!='summary'},ensure_ascii=False,indent=2)+
                '\n\n按clean/Q40及来源分组的mean/median/P90/max见D2_decision.json的summary。无成功终点不回退C0；覆盖不完整不能作为完整替代策略。绝不重判旧H5/H2/H3。\n')
    return comparisons,decision,caseindex,model


def polish(y,model,start,params,budget):
    """单次微型方法：没有真值入参；不返回救援后的旧实验结果。"""
    from scipy.optimize import minimize
    budget.start();trace=[];cache={}
    def objective(p):
        budget.evaluate()
        key=tuple(float(x) for x in p)
        if key not in cache:
            counter={'nnls_calls':0};cache[key]=evaluate_point(y,model,p,counter)
        trace.append(dict(position=list(key),objective=cache[key]['objective']))
        return cache[key]['objective']
    result=minimize(objective,start,method='Powell',bounds=[(-.5,.5)]*2,
                    options=dict(maxfev=params['maxfev'],xtol=params['xtol'],ftol=params['ftol']))
    if result.nfev>80:raise RuntimeError('D3 cap exceeded')
    key=tuple(float(x) for x in result.x)
    extra=0
    if key not in cache:
        c={'nnls_calls':0};cache[key]=evaluate_point(y,model,result.x,c);extra=c['nnls_calls']
    return dict(point=cache[key],success=bool(result.success),status=int(result.status),message=str(result.message),
                nfev=int(result.nfev),nit=int(result.nit),new_start=list(start),
                trace=trace,unique_NNLS_calls=len(cache),posterior_endpoint_extra_calls=extra)


def phase3(writer,d2,comparisons,cases,model,contract):
    if not d2['D3_needed']:
        status=dict(status='D3_SKIPPED',reason='D1来源回放与D2成功终点对照已提供两类机制的逐例定量证据；无需用新优化分辨主要案例。',
                    new_starts=0,new_function_evaluations=0,NNLS_calls=0)
    else:
        budget=core.MicroBudget();results=[];alltraces={};index={r['observation_id']:r for r in comparisons}
        for obs in contract['D3']['selected_ids']:
            c=cases[obs];row=index[obs];start=json.loads(row['C0_xy'])
            result=polish(c['y'],model,start,contract['D3'],budget)
            metrics=score(result['point'],c)
            results.append(dict(observation_id=obs,protocol=row['protocol'],C0_xy=row['C0_xy'],
                                C0_objective=row['C0_objective'],C1_xy=row['C1_xy'],C1_objective=row['C1_objective'],
                                polished_xy=json.dumps(result['point']['position']),objective=result['point']['objective'],
                                objective_change=result['point']['objective']-row['C0_objective'],
                                success=result['success'],status=result['status'],message=result['message'],
                                nfev=result['nfev'],nit=result['nit'],KKT=result['point']['KKT'],
                                boundary=max(map(abs,result['point']['position']))>=.5-1e-5,**metrics))
            alltraces[obs]=result
        writer.csv('micro_polish_cases.csv',results)
        writer.json('D3_traces.json',alltraces)
        status=dict(status='D3_EXECUTED_ONCE',new_starts=budget.starts,new_function_evaluations=budget.total,
                    NNLS_calls=sum(r['unique_NNLS_calls'] for r in alltraces.values()),
                    success=sum(r['success'] for r in results),
                    decreased=sum(r['objective_change'] < -contract['thresholds']['objective_abs_near'] for r in results),
                    old_H5_changed=False)
    writer.json('D3_status.json',status)
    writer.text('D3_summary.md',NOTICE+'\n\n'+json.dumps(status,ensure_ascii=False,indent=2)+'\n\n不得由该状态放行旧H5或full。\n')
    return status


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--task',type=Path,required=True);args=parser.parse_args()
    serial=1
    while (ROOT/f'reports/N03/EXP3R_H5_DIAG_20261021_{serial:02d}').exists():serial+=1
    out=ROOT/f'reports/N03/EXP3R_H5_DIAG_20261021_{serial:02d}'
    out.mkdir(exist_ok=False);(out/'logs').mkdir();(out/'logs/source_snapshot').mkdir()
    writer=OutputWriter(out);start=time.perf_counter();before=gitstate();frozen={};tests=[]
    stage='D0';error=None;d1=None;d2=None;d3=None;comparison=[];contract=None
    try:
        protected=[p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and
                   '__pycache__' not in p.parts and 'runtime_cache' not in p.parts and CODE not in p.parents and out not in p.parents]
        frozen={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in protected}
        writer.json('input_manifest.json',frozen)
        import torch
        writer.json('environment.json',dict(python=sys.version,executable=sys.executable,numpy=np.__version__,scipy=scipy.__version__,
                                           pytorch=torch.__version__,platform=platform.platform(),threads={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']}))
        if any(os.environ.get(k)!='4' for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']):raise RuntimeError('UNVERIFIED: canonical threads')
        rows,contract=phase0(writer,args.task,frozen,before)
        writer.text('logs/task_original.md',args.task.read_text(encoding='utf-8-sig'))
        event(writer,'D0_FROZEN',old_files=len(frozen),contract_sha256=sha(out/'diagnostic_contract.json'))
        stage='D1';b,audit,traces,d1=phase1(writer,rows,contract)
        event(writer,'D1_REPLAY_PASS',observations=d1['observations'],starts=d1['starts'],counts=d1['counts'])
        stage='D2';comparison,d2,cases,model=phase2(writer,b,audit,traces,contract)
        event(writer,'D2_COMPLETE',C1_valid=d2['C1_valid'],fixed_point_NNLS=d2['fixed_point_NNLS_calls'],label=d2['label'],D3_needed=d2['D3_needed'])
        stage='D3';d3=phase3(writer,d2,comparison,cases,model,contract)
        from tests_diag import checks
        tests.extend(checks(core,writer))
        tests.extend([dict(name='原48B/96起点/严格H5回放',passed=d1['passed']),
                      dict(name='固定位置目标独立重评价一致',passed=d2['all_objective_checks_pass']),
                      dict(name='D2每观测至多3个确定坐标且不优化',passed=d2['fixed_point_NNLS_calls']<=125),
                      dict(name='D3受控或未执行',passed=d3['new_starts']<=8 and d3['new_function_evaluations']<=640),
                      dict(name='未触发D3不得制造微型结果',passed=d3['status']!='D3_SKIPPED' or not (out/'micro_polish_cases.csv').exists())])
        stage='COMPLETE'
    except Exception:
        error=traceback.format_exc()
        writer.text('logs/failure_record.md',NOTICE+'\n\n```text\n'+error+'\n```\n')
        event(writer,'STOP_UNVERIFIED',stage_at_stop=stage,error=error.splitlines()[-1])
    finally:
        changed=[name for name,entry in frozen.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=entry['sha256']]
        after=gitstate();integrity=not changed and before['head']==after['head'] and before['tracked_diff_sha256']==after['tracked_diff_sha256']
        source_changed=[] if contract is None else [name for name,digest in contract['source_sha256'].items() if sha(ROOT/name)!=digest]
        tests.append(dict(name='旧文件/HEAD/tracked diff完全保持',passed=integrity,changed=changed))
        tests.append(dict(name='冻结新诊断源码未漂移',passed=not source_changed,changed=source_changed))
        oldgate=read(BASE/'pilot_gate.json')
        tests.append(dict(name='旧科研门仍FAIL',passed=oldgate['decision']=='EXP3R_PILOT_FAIL' and not oldgate['H5']['passed']))
        original_gate_hash=frozen.get(str((BASE/'pilot_gate.json').relative_to(ROOT)),{}).get('sha256')
        tests.append(dict(name='旧门文件逐字未改',passed=original_gate_hash==sha(BASE/'pilot_gate.json')))
        qa=all(t['passed'] for t in tests) and not error and stage=='COMPLETE'
        scientific=d2['label'] if d2 and qa else 'H5_DIAG_INCONCLUSIVE'
        observed=dict(B_observations=d1['observations'] if d1 else None,B_local_starts=d1['starts'] if d1 else None,
                      H5_exact_replay=d1['strict_H5_count'] if d1 else None,provenance_counts=d1['counts'] if d1 else None,
                      C1_available=d2['C1_valid'] if d2 else None,
                      no_successful_endpoint_cases=d2['no_endpoint_cases'] if d2 else None,
                      new_optimization_starts=d3['new_starts'] if d3 else 0)
        decision=dict(notice=NOTICE,decision=scientific,engineering_QA_passed=qa,observed=observed,
                      diagnostic_inference={k:d2[k] for k in ['semantic_close_cases','convergence_limited_cases','unresolved_cases','rule']} if d2 else {},
                      unverified=['光学PSF可信性和真实相机标定','全域唯一性','单seed以外的噪声泛化','未精修案例是否还能下降'],
                      old_gate_unchanged=True if integrity else False,old_H5='FAIL',full='NOT_RUN 0/504',
                      upstream={'N03_G0':'FAIL','N02_G2':'FAIL','N02_G3_Numerics':'FAIL'},
                      next_step='若独立审核确认这些来源和C1反事实，另立并预注册候选返回/收敛认证一致的单点pilot；本轮不改旧选择器、不放行full。' if qa else '证据不足或工程核验失败，暂停推进。')
        writer.json('diagnostic_decision.json',decision)
        writer.json('tests.json',tests)
        writer.json('postrun_checks.json',dict(unchanged=integrity,changed=changed,source_changed=source_changed,
                                              git_before=before,git_after=after,old_gate_sha256_before=original_gate_hash,
                                              old_gate_sha256_after=sha(BASE/'pilot_gate.json'),full_observations=0))
        if d3 is None:
            writer.json('D3_status.json',dict(status='D3_SKIPPED',reason='前置阶段停止或UNVERIFIED',new_starts=0,new_function_evaluations=0))
            writer.text('D3_summary.md',NOTICE+'\n\nD3_SKIPPED：前置阶段停止，未运行精修。\n')
        summary=NOTICE+'\n\n'+scientific+'\n\n旧EXP3R H2/H3/H4 PASS、H5 FAIL、full NOT_RUN 0/504永久保留。\n\n'
        summary+='实际阶段：'+json.dumps(dict(D0=contract is not None,D1=d1 is not None,D2=d2 is not None,D3=d3 if d3 else 'SKIPPED'),ensure_ascii=False)+'\n\n'
        summary+='Observed：'+json.dumps(observed,ensure_ascii=False,indent=2)+'\n\n'
        if d2:
            summary+='Diagnostic inference：'+json.dumps(decision['diagnostic_inference'],ensure_ascii=False,indent=2)+'\n\n'
            summary+='C0/C1 clean/Q40统计（均分列mean/median/P90/max，缺失终点不进入有效样本统计）：\n\n'
            for item in d2['summary']:
                if item['group']=='ALL':summary+='```json\n'+json.dumps(item,ensure_ascii=False,indent=2)+'\n```\n\n'
            summary+='真实可继续下降的直接证据：D2没有新优化，C1通常只能维持或增加C0的目标；未据此证明C0还能下降。缺少成功终点/预算耗尽只证明收敛认证受限。D3结果以D3_status为准。\n\n'
        summary+='原始逐例：provenance_audit.csv、termination_audit.csv、endpoint_only_comparison.csv、D2_objective_reverification.csv；旧H5逐字规则original_H5_verbatim.txt；精确回放h5_exact_replay.json。\n\n'
        summary+='工程QA：'+str(qa)+'；输入input_manifest；源码source_manifest与logs/source_snapshot；全部交付哈希final_manifest.json。\n\n'
        summary+='Unverified：'+ '；'.join(decision['unverified'])+'。\n\n'+decision['next_step']+'\n'
        if error:summary+='\n停止证据：logs/failure_record.md。\n'
        writer.text('results_summary.md',summary)
        writer.text('DELIVERY.md',summary)
        sources={}
        for p in CODE.glob('*.py'):
            dest=writer.path('logs/source_snapshot/'+p.name)
            with dest.open('xb') as h:h.write(p.read_bytes())
            sources[str(p.relative_to(ROOT))]=dict(sha256=sha(p),snapshot=str(dest.relative_to(out)))
        writer.json('source_manifest.json',sources)
        writer.json('logs/run_record.json',dict(status=scientific,engineering_QA=qa,stage=stage,seconds=time.perf_counter()-start,
                                              argv=sys.argv,observed=observed,error=error))
        writer.text('logs/run_commands.md','实际命令：\n\n'+subprocess.list2cmdline([sys.executable,'-B',*sys.argv])+'\n\n设置PYTHONDONTWRITEBYTECODE=1及OMP/MKL/OPENBLAS线程4；未运行旧实验入口。\n')
        writer.json('final_manifest.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
        print(json.dumps(dict(delivery=str(out/'DELIVERY.md'),decision=scientific,engineering_QA=qa,observed=observed),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
