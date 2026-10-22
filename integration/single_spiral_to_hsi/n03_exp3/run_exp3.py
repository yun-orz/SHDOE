"""预注册、先pilot后full、全部结果和输入保护归档。"""
import argparse
import csv
import hashlib
import importlib.util
import inspect
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import scipy
import ctypes
from forward_adapter import ForwardAdapter, ROOT, f, noise, sampling, perturbations
from position_solver import joint_solve, ALGORITHM

NOTICE='EXPLORATORY ONLY / optical G0 FAIL — archived B2 optical PSF is not full-domain numerically certified; image-plane shift-invariance is an approximation'
EXP2=ROOT/'reports/N03/EXP2_20261020_03'
EXP2B=ROOT/'reports/N03/EXP2B_CAL_TOL_20261021_01'
POSITIONS=[[0,0],[.10,0],[0,.25],[-.25,.20],[.40,-.35],[-.40,-.35],[.23,-.17]]
PILOT_POS=[0,1,3,4]
PILOT_SPECTRA=['onehot_420','onehot_660','near_equal','far_equal','broad_510','random_0']
SEEDS=[20261021,20261022,20261023]


def peak_memory():
    # 使用Windows已有接口读取峰值工作集，避免安装额外依赖。
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(name,ctypes.c_size_t) for name in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    handle=ctypes.windll.kernel32.GetCurrentProcess
    handle.restype=ctypes.c_void_p
    if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(handle()),ctypes.byref(counters),counters.cb):raise OSError('峰值内存读取失败')
    return counters.PeakWorkingSetSize


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def json_scalar(value):
    # 统计中的NumPy标量显式转换，保留原数值和预注册参数。
    if isinstance(value,np.generic):return value.item()
    raise TypeError(f'不支持JSON类型：{type(value)}')
def write(p,obj):
    with Path(p).open('x',encoding='utf-8') as h:json.dump(obj,h,ensure_ascii=False,indent=2,allow_nan=False,default=json_scalar)
def text(p,s):
    with Path(p).open('x',encoding='utf-8') as h:h.write(s)
def csvwrite(p,rows):
    with Path(p).open('x',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],encoding='utf-8').strip()
def event(out,stage,**kwargs):
    obj=dict(stage=stage,**kwargs)
    with (out/'logs/events.jsonl').open('a',encoding='utf-8') as h:h.write(json.dumps(obj,ensure_ascii=False,default=json_scalar)+'\n')
    print(json.dumps(obj,ensure_ascii=False,default=json_scalar),flush=True)


def aggregate(rows):
    groups={}
    for r in rows:
        for dimension,key in [('ALL','ALL'),('kind',r['kind']),('position',str(r['position_id'])),('seed',str(r['seed']))]:
            groups.setdefault((r['stage'],r['protocol'],r['method'],dimension,key),[]).append(r)
    result=[]
    for key,items in groups.items():
        obj=dict(zip(['stage','protocol','method','dimension','group'],key));obj['n']=len(items)
        obj.update(solver_fail_fraction=np.mean([r['solver_status']!='SUCCESS' for r in items]),boundary_fraction=np.mean([r['boundary'] for r in items]))
        for metric in ['position_error_pixel','position_error_nm','NRMSE','SAM_deg','energy_bias','relative_residual','kkt']:
            values=np.array([r[metric] for r in items],dtype=float)
            obj.update({metric+'_mean':float(np.mean(values)),metric+'_median':float(np.median(values)),metric+'_p90':float(np.quantile(values,.9)),metric+'_worst':float(np.max(np.abs(values)))})
        obj['fraction_NRMSE_le_0.01']=float(np.mean([r['NRMSE']<=.01 for r in items]));result.append(obj)
    return result


def observations(out,model,spectra,stage,indices,positions,seeds,rows,traces):
    started=time.perf_counter();peak=0
    for pi in positions:
        position=POSITIONS[pi];a,capture=model.matrix(position, .10 if stage=='mismatch' else 0.)
        oracle_a,_=model.matrix(position);oracle=f.Operator(oracle_a);fixed=f.Operator(model.matrix((0,0))[0])
        for si in indices:
            case=spectra[si];truth=np.array(case['truth']);clean=a@truth
            for seed in seeds:
                y=clean if seed==0 else noise.protocol_q(clean,noise.gaussian_direction(seed,si,len(clean)),40)[0]
                snr=noise.realized_snr(clean,y)
                if seed and abs(snr-40)>1e-8:raise ArithmeticError('Q40实际SNR失败')
                obs=f'{stage}_{pi}_{si}_{seed}';begin=time.perf_counter()
                try:
                    joint=joint_solve(y,model);traces[obs]=joint['trace']
                    solved=[('O',position,*oracle.solve(y)),('F',[0,0],*fixed.solve(y)),('J',joint['position'],joint['estimate'],np.sqrt(joint['loss']),joint['kkt'])]
                except Exception as exc:
                    event(out,'SOLVER_FAILURE',observation=obs,error=repr(exc));raise
                for method,p,estimate,res,kkt in solved:
                    quality=f.SOLVERS.spectral_metrics(truth,estimate,f.WAVES)
                    ep=float(np.linalg.norm(np.array(p)-position))
                    rows.append(dict(stage=stage,observation=obs,spectrum=case['name'],spectrum_index=si,kind=case['kind'],position_id=pi,protocol='noiseless' if seed==0 else 'Q40',seed=seed,method=method,
                                     dx_true=position[0],dy_true=position[1],dx_hat=p[0],dy_hat=p[1],position_error_pixel=ep,position_error_nm=ep*model.pitch*1000,
                                     NRMSE=quality['spectral_NRMSE'],SAM_deg=quality['SAM_deg'],energy_bias=quality['relative_amplitude_bias'],relative_residual=res,kkt=kkt,
                                     y_norm=float(np.linalg.norm(y)),recovered_energy=float(estimate.sum()),actual_SNR_db=snr,solver_status='SUCCESS',boundary=bool(max(abs(np.array(p)))>=.5-1e-5),
                                     truth=json.dumps(truth.tolist()),estimate=json.dumps(estimate.tolist()),noise_sha256=hashlib.sha256((y-clean).tobytes()).hexdigest(),
                                     capture=json.dumps(capture.tolist()),evaluations=joint['trace']['evaluations'] if method=='J' else 1,seconds=time.perf_counter()-begin))
                peak=max(peak,peak_memory())
        event(out,'POSITION_COMPLETE',stage_name=stage,position_id=pi,rows=len(rows),seconds=time.perf_counter()-started)
    return dict(seconds=time.perf_counter()-started,peak_memory_bytes=peak,max_evaluations=max(v['evaluations'] for k,v in traces.items() if k.startswith(stage+'_')))


def figures(out,rows,model,spectra):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    main=[r for r in rows if r['stage']==('full' if any(t['stage']=='full' for t in rows) else 'pilot')]
    j=[r for r in main if r['method']=='J']
    def save(fig,name):
        fig.suptitle('EXPLORATORY ONLY / optical G0 FAIL',fontsize=11)
        fig.tight_layout(rect=(0,.02,1,.94));fig.savefig(out/'figures'/name,dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,key,true in zip(axes,['dx_hat','dy_hat'],['dx_true','dy_true']):
        for protocol in ['noiseless','Q40']:
            rr=[r for r in j if r['protocol']==protocol];ax.scatter([r[true] for r in rr],[r[key] for r in rr],s=8,label=protocol,alpha=.5)
        ax.plot([-.5,.5],[-.5,.5],'k--');ax.set(xlabel=true+' (pixel)',ylabel=key+' (pixel)');ax.legend()
    save(fig,'unknown_position_scatter.png')
    fig,ax=plt.subplots(figsize=(8,4))
    for protocol in ['noiseless','Q40']:
        rr=[r for r in j if r['protocol']==protocol];ax.scatter([r['position_id'] for r in rr],[r['position_error_pixel'] for r in rr],s=9,label=protocol)
    ax.set(xlabel='Pre-registered position ID',ylabel='Position error (pixel)');ax.legend();save(fig,'position_error_by_offset.png')
    fig,ax=plt.subplots(figsize=(8,4))
    vals=[[r['NRMSE'] for r in main if r['method']==m and r['protocol']==p] for p in ['noiseless','Q40'] for m in ['O','F','J']]
    ax.boxplot([np.maximum(v,1e-16) for v in vals],tick_labels=[p+'/'+m for p in ['clean','Q40'] for m in ['O','F','J']]);ax.set_yscale('log');ax.set_ylabel('Spectral NRMSE');save(fig,'spectral_error_oracle_fixed_joint.png')
    best=min(j,key=lambda r:r['position_error_pixel']);worst=max(j,key=lambda r:r['position_error_pixel'])
    fig,axes=plt.subplots(1,2,figsize=(11,4));maps=[]
    for ax,r in zip(axes,[best,worst]):
        p=np.array([r['dx_true'],r['dy_true']]);truth=np.array(json.loads(r['truth']));a,_=model.matrix(p);clean=a@truth
        y=clean if r['seed']==0 else noise.protocol_q(clean,noise.gaussian_direction(r['seed'],r['spectrum_index'],len(clean)),40)[0]
        xs=np.linspace(max(-.5,p[0]-.08),min(.5,p[0]+.08),17);ys=np.linspace(max(-.5,p[1]-.08),min(.5,p[1]+.08),17)
        z=np.empty((17,17))
        for iy,dy in enumerate(ys):
            for ix,dx in enumerate(xs):z[iy,ix]=f.Operator(model.matrix((dx,dy))[0]).solve(y)[1]**2
        ax.imshow(np.log10(np.maximum(z,1e-32)),origin='lower',extent=[xs[0],xs[-1],ys[0],ys[-1]],aspect='auto');ax.plot(*p,'w+');ax.plot(r['dx_hat'],r['dy_hat'],'rx');ax.set(title=r['spectrum']+'/'+r['protocol'],xlabel='dx (pixel)',ylabel='dy (pixel)')
        maps.append(dict(observation=r['observation'],x=xs.tolist(),y=ys.tolist(),relative_squared_residual=z.tolist()))
    save(fig,'objective_map_best_worst.png');write(out/'objective_maps.json',maps)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,r in zip(axes,[max(j,key=lambda t:t['NRMSE']),worst]):
        ax.plot(f.WAVES,json.loads(r['truth']),'k--',label='truth')
        for item in main:
            if item['observation']==r['observation']:ax.plot(f.WAVES,json.loads(item['estimate']),label=item['method'])
        ax.set(title=r['spectrum']+'/'+r['protocol'],xlabel='Wavelength (nm)',ylabel='Integrated band energy');ax.legend()
    save(fig,'example_spectra.png')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);(out/'logs').mkdir();(out/'figures').mkdir()
    start=time.perf_counter();before=dict(head=git('rev-parse','HEAD'),status=git('status','--short'),diff=hashlib.sha256(subprocess.check_output(['git','diff','--binary'],cwd=ROOT)).hexdigest())
    # 在创建任何新产物前保护所有既有研究结果及源码；不对旧目录写缓存。
    protected=[]
    for folder in ['reports','optics','integration','framework/DeepLensHSI/sensors','provenance']:
        protected += [p for p in (ROOT/folder).rglob('*') if p.is_file() and out not in p.parents and 'n03_exp3' not in p.parts and p.name!='test_n03_exp3.py' and '.git' not in p.parts and '__pycache__' not in p.parts]
    protected += [ROOT/'README.md']
    manifest={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in protected};write(out/'input_manifest.json',manifest)
    for folder,name in [(EXP2,'final_manifest.json'),(EXP2B,'artifact_manifest.json')]:
        bad=[n for n,h in read(folder/name).items() if sha(folder/n)!=h]
        if bad:raise RuntimeError(f'冻结归档哈希失败{bad}')
    model=ForwardAdapter();old=read(EXP2/'run_config.json');ref=read(EXP2B/'run_config.json')
    assert old['wavelengths_nm']==[420,450,480,510,540,570,600,630,660]
    assert read(ROOT/'reports/N03/00_manifest.json')['decision']=='G0_FAIL_STOP'
    gates=read(ROOT/'optics/n02_single_spiral/results/n02/n02_20261019_02/gates.json')
    assert gates['G2']['status']==gates['G3_Numerics']['status']=='FAIL'
    interfaces={fn.__qualname__:dict(file=inspect.getsourcefile(fn),line=inspect.getsourcelines(fn)[1]) for fn in [f.load,f.matrix,f.Operator.solve,sampling.overlap_matrix,sampling.gaussian_overlap_matrix,perturbations.detector_perturb,noise.protocol_q]}
    config=dict(notice=NOTICE,created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),algorithm=ALGORITHM,positions=POSITIONS,pilot_positions=PILOT_POS,pilot_spectra=PILOT_SPECTRA,seeds=SEEDS,
                thresholds=dict(clean_position=.005,Q40_position=.02,Q40_fraction_spectrum=.8,NRMSE=.01),environment=dict(python=sys.version,executable=sys.executable,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),device='CPU',threads=4),
                git_before=before,interfaces=interfaces,wavelengths=old['wavelengths_nm'],weights_RGB=model.weights.tolist(),detector=old['detector'],spectra=old['spectra'],normalization='EXP2/EXP2B逐带detector capture归一shape_only；无整图归一、无Delta-lambda；逐位置capture完整记录',full_max_projected_seconds=3600)
    write(out/'run_config.json',config)
    text(out/'00_preflight.md','# G3-0 只读预检 PASS\n\n'+NOTICE+'\n\nEXP2 final_manifest及EXP2B artifact_manifest逐项核验通过。全部既有reports、optics、integration源码、传感器和README已冻结SHA-256，见input_manifest。HEAD及原dirty状态见run_config。原N03 G0与N02 G2/G3_Numerics保持FAIL。\n\n接口真实文件和行号见run_config.interfaces。归档512方格为1 μm分片常数像元，中心index−255.5，边界−256至256 μm；光轴在四格交点，186偶数detector的光轴也是四格交点，不假设有唯一中心像素。pitch=2.7397868561278864 μm；正dx向列增加，正dy向行增加。对源边界加(dx,dy)*pitch，零延拓，无周期绕回。固定ROI、物理RGB通道优先展平。s是九个离散带积分能量。\n\n连续双轴位移使用EXP2B所调用的overlap_matrix/rebin原函数。逐带shape_only归一严格沿用EXP2B，并记录每个位置的归一前capture；该定义舍弃位置引起的裁切通量，不添加RGB整体增益自由度。不是光学传播重认证。\n\n算法与阈值先于实验冻结：3×3粗网格，最低残差两个起点各55次Powell，最多119候选。单例只有y和固定模型输入。pilot48观测，full504观测；预计full超过3600秒则PARTIAL停止。\n')
    testpath=ROOT/'integration/single_spiral_to_hsi/tests/test_n03_exp3.py';spec=importlib.util.spec_from_file_location('test_exp3',testpath);test=importlib.util.module_from_spec(spec);spec.loader.exec_module(test)
    checks=test.checks(model,ref)
    diagnostics={}
    for p in [[0,0],[-.5,0],[.5,0],[0,-.5],[0,.5],[.23,-.17]]:diagnostics[str(p)]=f.diagnostic(f.Operator(model.matrix(p)[0]))
    write(out/'matrix_diagnostics.json',diagnostics)
    if not all(c['passed'] for c in checks):write(out/'tests.json',checks);raise RuntimeError('G3-1测试失败')
    rows=[];traces={};spectra=old['spectra'];pilot_indices=[i for i,s in enumerate(spectra) if s['name'] in PILOT_SPECTRA]
    event(out,'G3_1_PASS',tests=len(checks))
    pilot=observations(out,model,spectra,'pilot',pilot_indices,PILOT_POS,[0,SEEDS[0]],rows,traces)
    pj=[r for r in rows if r['method']=='J'];clean=[r for r in pj if r['seed']==0];q=[r for r in pj if r['seed']]
    regress=[]
    with (EXP2/'metrics.csv').open(encoding='utf-8-sig',newline='') as h:oldrows=list(csv.DictReader(h))
    for r in rows:
        if r['position_id']==0 and r['method']=='O':
            original=next(o for o in oldrows if o['model']==f.MODELS[2] and o['shape_mode']=='shape_only' and o['spectrum']==r['spectrum'] and int(o['seed'])==r['seed'] and (r['seed']==0 or (o['protocol']=='Q' and float(o['target_SNR_db'])==40)))
            regress.append(float(np.max(np.abs(np.array(json.loads(r['estimate']))-json.loads(original['estimate'])))))
    checks.append(dict(name='EXP2原点oracle逐例回归',passed=max(regress)<1e-12,value=max(regress),limit=1e-12))
    q_worse=sum(r['relative_residual']>next(t['relative_residual'] for t in rows if t['observation']==r['observation'] and t['method']=='F')+1e-10 for r in q)
    pilot_pass=all(c['passed'] for c in checks) and max(r['position_error_pixel'] for r in clean)<=.005 and q_worse==0 and not all(r['boundary'] for r in q)
    projected=pilot['seconds']*504/48
    decision=dict(**pilot,passed=pilot_pass,clean_worst_position=max(r['position_error_pixel'] for r in clean),Q40_worse_than_F=q_worse,projected_full_seconds=projected)
    write(out/'pilot_gate.json',decision);csvwrite(out/'pilot_metrics.csv',rows);event(out,'PILOT_GATE',**decision)
    full_run=pilot_pass and projected<=3600
    timing={'pilot':pilot}
    if full_run:
        timing['full']=observations(out,model,spectra,'full',list(range(18)),list(range(7)),[0]+SEEDS,rows,traces)
        # 失配仅调用已验收的连续高斯积分，名义oracle和J均不知道宽度。
        timing['mismatch']=observations(out,model,spectra,'mismatch',pilot_indices,PILOT_POS,[0],rows,traces)
    csvwrite(out/'metrics.csv',rows);csvwrite(out/'comparison_summary.csv',aggregate(rows));write(out/'optimization_traces.json',traces)
    figures(out,rows,model,spectra)
    stage='full' if full_run else 'pilot';mainrows=[r for r in rows if r['stage']==stage];js=[r for r in mainrows if r['method']=='J'];clean=[r for r in js if r['seed']==0];q=[r for r in js if r['seed']]
    clean_med=float(np.median([r['position_error_pixel'] for r in clean]));q_med=float(np.median([r['position_error_pixel'] for r in q]));fraction=float(np.mean([r['NRMSE']<=.01 for r in q]));target=clean_med<=.005 and q_med<=.02 and fraction>=.8
    status=('PASS' if target else 'CONDITIONAL') if full_run else ('PARTIAL' if pilot_pass else 'STOP_G3_2')
    checks.append(dict(name='样本完整唯一',passed=len(set((r['observation'],r['method']) for r in rows))==len(rows) and len(mainrows)==(1512 if full_run else 144),value=len(mainrows)))
    unchanged=[p for p,v in manifest.items() if sha(ROOT/p)!=v['sha256']]
    diff=hashlib.sha256(subprocess.check_output(['git','diff','--binary'],cwd=ROOT)).hexdigest()
    checks.append(dict(name='所有冻结输入与已有tracked差异保持',passed=not unchanged and diff==before['diff'],changed=unchanged))
    write(out/'tests.json',checks)
    comparisons={}
    for protocol in ['noiseless','Q40']:
        rr=[r for r in mainrows if r['protocol']==protocol]
        comparisons[protocol]={m:dict(NRMSE_median=float(np.median([r['NRMSE'] for r in rr if r['method']==m])),NRMSE_worst=max(r['NRMSE'] for r in rr if r['method']==m),position_median=float(np.median([r['position_error_pixel'] for r in rr if r['method']==m]))) for m in ['O','F','J']}
    write(out/'paired_comparison.json',comparisons)
    worst=max(js,key=lambda r:r['NRMSE'])
    summary=f'# EXP3结果：{status}\n\n{NOTICE}\n\nG3-0/G3-1 PASS；G3-2 {"PASS" if pilot_pass else "FAIL"}；G3-3 {status if full_run else "NOT_RUN"}；G3-4 {"RUN_24_NOISELESS" if full_run else "NOT_RUN"}；G3-5 {"PASS" if all(c["passed"] for c in checks) else "FAIL"}。\n\nAlgorithm implementation：连续面积积分、RGB、目标、KKT与原点oracle回归通过；候选预算119，所有局部终止原因及次优候选见optimization_traces。预算终止与NNLS失败分开记录，局部停止不证明全局最优。\n\nBlind subpixel localization：{stage}无噪声中位误差{clean_med:.8g} pixel；Q40中位误差{q_med:.8g} pixel。像面nm换算乘{model.pitch*1000:.12g}；仅粗ROI已知的单点定位。\n\nSpectral reconstruction：Q40中J的NRMSE≤0.01比例{fraction:.3%}。各O/F/J中位与最坏值见paired_comparison.json；按类别、位置、seed的mean/median/P90/worst见comparison_summary.csv。最坏谱{worst["spectrum"]}，位置ID={worst["position_id"]}，seed={worst["seed"]}，NRMSE={worst["NRMSE"]:.8g}。\n\nOptical physics：N02 G2/G3_Numerics、N03 G0保持FAIL。无噪声为同模型自洽；失配24例仅为固定sigma=0.10 pixel合成展宽，O也使用错误名义模型，不代表实机性能。\n\npilot耗时{pilot["seconds"]:.2f}秒，峰值内存{pilot["peak_memory_bytes"]/2**20:.1f}MiB，预计full {projected:.1f}秒；full预算3600秒。全部输入未改核验={not unchanged}。目标函数二维图为最好/最坏定位案例局部17×17采样，不能排除采样间或全域其他极小值；第二候选仅为搜索中距离最优>0.01 pixel的候选，不是经认证的独立模态。\n'
    text(out/'result_summary.md',summary)
    text(out/'DELIVERY.md',f'# EXP3交付 {status}\n\n{NOTICE}\n\n阅读[result_summary.md](result_summary.md)，原始逐观测O/F/J结果在metrics.csv，pilot_gate.json给出full启动依据。代码在integration/single_spiral_to_hsi/n03_exp3，测试在tests/test_n03_exp3.py。未提交或推送Git；旧输入、README及物理门保留原状。本轮停止。\n')
    command=subprocess.list2cmdline([sys.executable,'-B',*sys.argv]);text(out/'logs/run_commands.md',command+'\n\nOMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=4; PYTHONDONTWRITEBYTECODE=1\n复跑必须指定新目录。\n')
    write(out/'logs/run_record.json',dict(status=status,seconds=time.perf_counter()-start,timing=timing,command=command,rows=len(rows),observations=len(rows)//3,git_before=before,git_after=git('status','--short'),environment=config['environment']))
    write(out/'postrun_checks.json',dict(inputs_unchanged=not unchanged,tracked_diff_unchanged=diff==before['diff'],all_tests_pass=all(c['passed'] for c in checks),N03_G0='FAIL',N02_G2='FAIL',N02_G3_Numerics='FAIL'))
    sources=list(Path(__file__).parent.glob('*.py'))+[testpath];(out/'logs/source_snapshot').mkdir()
    for p in sources:(out/'logs/source_snapshot'/p.name).write_bytes(p.read_bytes())
    write(out/'source_manifest.json',{str(p.relative_to(ROOT)):sha(p) for p in sources})
    event(out,'DELIVERED',status=status,rows=len(rows))
    write(out/'artifact_manifest.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})


if __name__=='__main__':main()
