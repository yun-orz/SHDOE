"""只读复核EXP3产物哈希、逐观测配对、统计及可复现指标。"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from run_exp3 import ROOT, sha, read, aggregate


def verify(out):
    failures=[]
    for name,digest in read(out/'artifact_manifest.json').items():
        if sha(out/name)!=digest:failures.append('产物哈希:'+name)
    for name,item in read(out/'input_manifest.json').items():
        if sha(ROOT/name)!=item['sha256']:failures.append('输入哈希:'+name)
    for name,digest in read(out/'source_manifest.json').items():
        if sha(ROOT/name)!=digest:failures.append('源码哈希:'+name)
    with (out/'metrics.csv').open(encoding='utf-8-sig',newline='') as h:raw=list(csv.DictReader(h))
    rows=[];groups={}
    numeric=['position_error_pixel','position_error_nm','NRMSE','SAM_deg','energy_bias','relative_residual','kkt','dx_true','dy_true','dx_hat','dy_hat']
    for r in raw:
        r=dict(r)
        for key in numeric:r[key]=float(r[key])
        r['boundary']=r['boundary']=='True';rows.append(r);groups.setdefault(r['observation'],[]).append(r)
        s=np.array(json.loads(r['estimate']));truth=np.array(json.loads(r['truth']))
        if abs(np.linalg.norm(s-truth)/np.linalg.norm(truth)-r['NRMSE'])>1e-12:failures.append('NRMSE:'+r['observation'])
        if abs(np.hypot(r['dx_hat']-r['dx_true'],r['dy_hat']-r['dy_true'])-r['position_error_pixel'])>1e-12:failures.append('位置误差:'+r['observation'])
        if r['protocol']=='Q40' and abs(float(r['actual_SNR_db'])-40)>1e-8:failures.append('Q40:'+r['observation'])
    for obs,items in groups.items():
        if sorted(r['method'] for r in items)!=['F','J','O'] or len(set(r['noise_sha256'] for r in items))!=1:failures.append('对照配对:'+obs)
    with (out/'comparison_summary.csv').open(encoding='utf-8-sig',newline='') as h:saved=list(csv.DictReader(h))
    computed=aggregate(rows)
    if len(saved)!=len(computed):failures.append('聚合行数')
    for a,b in zip(saved,computed):
        for key,value in b.items():
            if isinstance(value,(float,np.floating,int)) and abs(float(a[key])-value)>1e-12:failures.append('聚合:'+key)
    traces=read(out/'optimization_traces.json')
    if any(t['evaluations']>119 or t['nnls_calls']!=len(t['candidates']) for t in traces.values()):failures.append('定位预算')
    stages={stage:sum(r['stage']==stage for r in rows)//3 for stage in set(r['stage'] for r in rows)}
    expected={'pilot':48,'full':504,'mismatch':24}
    for stage,count in stages.items():
        if expected[stage]!=count:failures.append('观测完整性:'+stage)
    return dict(passed=not failures,failures=failures,observations=stages,rows=len(rows),recomputed_statistics=len(computed))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    result=verify(args.output);print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
