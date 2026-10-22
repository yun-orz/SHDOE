"""N02 可复算入口：先审计/测试/smoke，再固定高度标准波段与蓝端。"""
import sys
sys.dont_write_bytecode=True
import argparse
import json
import time
import traceback
import os
import stat
import numpy as np
from pathlib import Path
from optics import *
from audit import audit, write, textfile, now, snapshot, git
from physics_tests import run_tests
from evaluate import csvwrite, evaluate, plot_candidate

STANDARD=list(range(420,661,10))


def event(out, **record):
    with (out/'propagation_ledger.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(dict(time=now(),**record),ensure_ascii=False,allow_nan=False)+'\n')


def save_case(path, raw, coord, rec):
    with Path(path).open('xb') as stream:
        np.savez_compressed(stream,raw_roi=raw,normalized_psf=raw/raw.sum(),coords_um=coord,
                            record_json=json.dumps(rec,ensure_ascii=False,allow_nan=False))


def acquire_case(out, folder, d, h, w, cfg, **kwargs):
    target=folder/'cases'/f'{w:g}nm.npz'
    if target.exists():
        raise FileExistsError(f'禁止覆盖：{target}')
    event(out,event='START',candidate=cfg['candidate_id'],wavelength_nm=w,config=cfg,options=kwargs,height_sha=array_sha(h))
    try:
        raw,c,r=propagate(d,h,w,cfg,**kwargs)
        save_case(target,raw,c,r)
        event(out,event='COMPLETE',candidate=cfg['candidate_id'],wavelength_nm=w,path=str(target.relative_to(out)),
              sha256=sha(target),seconds=r['seconds'],gpu_peak_bytes=r.get('gpu_peak_allocated_bytes'),status=r['n02_status'])
        print(f"{cfg['candidate_id']} {w:g}nm N01={r['n01_status']} N02={r['n02_status']} ratio={r['outside_main_disk_ratio']:.5f} angle={r['raw_angle_deg']:.5f} ROI={r['crop_fraction']:.6f} {r['seconds']:.2f}s",flush=True)
        return raw,c,r
    except Exception:
        event(out,event='ERROR',candidate=cfg['candidate_id'],wavelength_nm=w,traceback=traceback.format_exc())
        raise


def make_folder(out,name,cfg,d,continuous=False):
    folder=out/name
    (folder/'cases').mkdir(parents=True,exist_ok=False)
    write(folder/'config.json',cfg)
    for filename,arr in [('height_um.npy',d['height']),('aperture_mask.npy',d['mask'])]:
        with (folder/filename).open('xb') as f:np.save(f,arr)
    lev,cnt=np.unique(d['height'][d['mask']],return_counts=True)
    if continuous:
        cnt,edges=np.histogram(d['height'][d['mask']],bins=100)
        hist=[dict(bin_left_um=float(a),bin_right_um=float(b),count=int(c)) for a,b,c in zip(edges,edges[1:],cnt)]
    else:hist=[dict(height_um=float(h),count=int(n)) for h,n in zip(lev,cnt)]
    csvwrite(folder/'height_histogram.csv',hist)
    write(folder/'height_metadata.json',dict(period_um=d['period_um'],max_height_um=float(d['height'].max()),
         height_sha256=sha(folder/'height_um.npy'),aperture_sha256=sha(folder/'aperture_mask.npy'),
         array_sha256=array_sha(d['height']),continuous=continuous,soft_low_amplitude_fraction=d['soft_low_amplitude_fraction']))
    return folder


def execute(out):
    t=time.perf_counter()
    env=audit(out)
    write(out/'source_hashes_initial.json',{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/n02').glob('*.py')})
    if not run_tests(out):
        write(out/'G0.json',dict(status='FAIL',reason='物理测试失败，后续停止'))
        return
    write(out/'G0.json',dict(status='PASS',reason='审计/冻结协议/12项隔离物理测试通过'))
    cfg=config()
    np.random.seed(cfg['seed']);torch.manual_seed(cfg['seed'])
    # smoke 保持真实孔径，缩小输入窗口但不用于最终判据。
    smoke_cfg=dict(cfg,size=1024,candidate_id='smoke_B2')
    d=design(smoke_cfg);folder=make_folder(out,'smoke_B2',smoke_cfg,d)
    for w in [420,546.1,660]:acquire_case(out,folder,d,d['height'],w,smoke_cfg)
    summaries={}
    for name,continuous,hand,spiral in [('B0',False,1,False),('B1',True,1,True),('B2',False,1,True),('B3',False,-1,True)]:
        cc=dict(cfg,candidate_id=name,handedness=hand)
        d=design(cc,spiral=spiral,continuous=continuous)
        folder=make_folder(out,name,cc,d,continuous)
        for w in STANDARD+[546.1]:acquire_case(out,folder,d,d['height'],w,cc)
        rows,links,s,images=evaluate(folder,cc,STANDARD)
        plot_candidate(folder,rows,links,s,images)
        summaries[name]=s
        del images,d
    write(out/'baseline_summaries.json',summaries)
    bcfg=dict(cfg,candidate_id='B2')
    d=design(bcfg)
    stored=np.load(out/'B2/height_um.npy',allow_pickle=False);stored.setflags(write=False)
    assert np.array_equal(stored,d['height'])
    blue=list(range(420,501,5));folder=out/'B2'
    for w in blue:
        if w not in STANDARD:acquire_case(out,folder,d,stored,w,bcfg)
    rows,links,s,images=evaluate(folder,bcfg,blue,tag='dense_blue')
    suspect=set()
    for i in links:
        a=next(r for r in rows if r['wavelength_nm']==i['from_nm'])
        b=next(r for r in rows if r['wavelength_nm']==i['to_nm'])
        if min(a['outside_main_disk_ratio'],b['outside_main_disk_ratio'])<1.60 or a['n02_status']=='FAIL' or b['n02_status']=='FAIL' or not i['main_link_unique']:
            suspect.update(range(int(i['from_nm'])+1,int(i['to_nm'])))
    new=sorted(suspect)[:80]
    write(out/'blue_adaptive_plan.json',dict(wavelengths_nm=new,rule='protocol_frozen.json中预注册规则',max_new_points=80))
    for w in new:
        if not (folder/'cases'/f'{w:g}nm.npz').exists():acquire_case(out,folder,d,stored,w,bcfg)
    if new:evaluate(folder,bcfg,sorted(set(blue+new)),tag='adaptive_blue')
    textfile(out/'completion_summary_batch1.md',f"# 批次1完成\n\nG0 PASS；B0/B1/B2/B3各25标准波长+546.1nm真实传播完成；B2 G1物理={summaries['B2']['G1_physical']}，形态={summaries['B2']['G1_single_lobe']}，G2={summaries['B2']['G2']}。\n结果见各候选standard_metrics.csv、standard_links.csv、图像及原始cases。失败未过滤；蓝端17点与自适应{len(new)}点已运行。\n")
    # 独立关键验证与工艺扫描放在后续模块，禁止跨门禁直接优化。
    from validation import validate
    validate(out,bcfg)
    from reporting import finalize
    finalize(out,env,t)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    if '/' in args.run_id or '\\' in args.run_id or '..' in args.run_id:raise ValueError('run-id必须是单一目录名')
    out=ROOT/'results/n02'/args.run_id
    out.mkdir(parents=True,exist_ok=False)
    write(out/'invocation.json',dict(time=now(),argv=sys.argv,python=sys.executable))
    try:execute(out)
    except Exception:
        textfile(out/'failure_traceback.txt',traceback.format_exc())
        print(traceback.format_exc(),flush=True)
        raise
