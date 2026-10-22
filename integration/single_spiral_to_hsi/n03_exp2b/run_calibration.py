"""A：固定EXP2名义字典的17个唯一位置、1224次NNLS标定容差。"""
import argparse
import importlib.util
import inspect
import traceback
from collections import defaultdict
from common import *

sys.path.insert(0,str(ROOT/'integration/single_spiral_to_hsi/n03_exp2'))
import forward as exp2f
import sampling as exp2s
import perturbations as exp2p
import noise as exp2n
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def aggregate(rows):
    result=[]
    for kind in ['ALL','onehot','double','broad','random']:
        groups=defaultdict(list)
        for r in rows:
            if kind=='ALL' or r['kind']==kind:groups[(r['position_id'],r['protocol'])].append(r)
        for (position,protocol),items in groups.items():
            first=items[0];record={k:first[k] for k in ['position_id','axis','signed_pixel','signed_um','signed_nm','sign']}
            record.update(protocol=protocol,spectrum_kind=kind,n=len(items),spectra=len(set(r['spectrum'] for r in items)),seeds=len(set(r['seed'] for r in items)))
            for metric in ['NRMSE','SAM_deg','relative_amplitude_bias','relative_sensor_residual']:
                values=np.array([r[metric] for r in items],dtype=float)
                seedmeans=[float(np.mean([r[metric] for r in items if r['seed']==seed])) for seed in sorted(set(r['seed'] for r in items))]
                record.update({metric+'_mean':float(values.mean()),metric+'_median':float(np.median(values)),metric+'_p90':float(np.quantile(values,.9)),
                               metric+'_max':float(values.max()),metric+'_across_sample_sd':float(values.std(ddof=1)),
                               metric+'_seed_mean_sd':float(np.std(seedmeans,ddof=1)) if len(seedmeans)>1 else 0.,metric+'_seed_means':json.dumps(seedmeans)})
            worst=max(items,key=lambda r:r['NRMSE']);record.update(worst_spectrum=worst['spectrum'],worst_seed=worst['seed'])
            for t in [.005,.01,.02]:record[f'fraction_NRMSE_gt_{t:g}']=float(np.mean([r['NRMSE']>t for r in items]))
            result.append(record)
    return result


def tolerance_intervals(summary):
    result=[]
    allrows=[r for r in summary if r['spectrum_kind']=='ALL']
    for protocol in ['noiseless','Q40']:
        zero=next(r for r in allrows if r['axis']=='origin' and r['protocol']==protocol)
        for axis in ['x','y']:
            for sign in ['negative','positive']:
                items=sorted([r for r in allrows if r['protocol']==protocol and r['axis']==axis and r['sign']==sign],key=lambda r:abs(r['signed_pixel']))
                sequence=[zero]+items
                for threshold in [.005,.01,.02]:
                    for stat in ['mean','median','p90','max']:
                        values=[r['NRMSE_'+stat] for r in sequence]
                        first=next((i for i,v in enumerate(values) if v>threshold),None)
                        if first is None:lower,upper,status=.05,None,'NO_CROSSING_IN_TESTED_GRID'
                        elif first==0:lower,upper,status=0.,0.,'BASELINE_ALREADY_EXCEEDS'
                        else:lower,upper,status=abs(sequence[first-1]['signed_pixel']),abs(sequence[first]['signed_pixel']),'FIRST_DISCRETE_CROSSING'
                        pitch=abs(items[0]['signed_um']/items[0]['signed_pixel'])
                        result.append(dict(protocol=protocol,axis=axis,sign=sign,statistic=stat,threshold=threshold,
                                           lower_abs_pixel=lower,upper_abs_pixel=upper,lower_abs_um=lower*pitch,upper_abs_um=upper*pitch if upper is not None else None,
                                           lower_abs_nm=lower*pitch*1000,upper_abs_nm=upper*pitch*1000 if upper is not None else None,
                                           status=status,monotonic_on_tested_grid=all(b>=a-1e-12 for a,b in zip(values,values[1:])),
                                           values_in_abs_shift_order=json.dumps(values),tested_abs_pixel=json.dumps([0,.005,.01,.02,.05])))
    return result


def plot_finish(fig,path,title,pitch):
    fig.suptitle(title,fontsize=11);fig.text(.5,.012,NOTICE,ha='center',fontsize=7)
    for ax in fig.axes:
        if ax.get_xlabel()=='Signed shift (pixel)':
            top=ax.secondary_xaxis('top',functions=(lambda x:x*pitch,lambda x:x/pitch));top.set_xlabel('Signed shift (um)',fontsize=8)
    fig.tight_layout(rect=(0,.06,1,.9));fig.savefig(path,dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    out=new_output(parser.parse_args().output);started=time.perf_counter();before=gitstate();rows=[];estimates=[]
    try:
        verify_exp2();old=read(EXP2/'run_config.json');oldmetrics=csvread(EXP2/'metrics.csv')
        olddiagnostics=read(EXP2/'matrices_9band.json');read(EXP2/'matrices_25band_diagnostic.json');read(EXP2/'input_manifest.json')
        for n in ['DELIVERY.md','result_summary.md','interpretation_addendum.md']:(EXP2/n).read_text(encoding='utf-8')
        fine,weights,assets,records,indices,pitch=exp2f.load(ROOT)
        edges,det_edges,overlap=exp2s.centered_grid(512,pitch)
        cube=exp2s.rebin_cube(fine[exp2f.MODELS[2]],overlap);nominal_capture=cube.sum(axis=(1,2));cube/=nominal_capture[:,None,None]
        nominal=exp2f.Operator(exp2f.matrix(cube,weights));nominal_hash=hashlib.sha256(nominal.a.tobytes()).hexdigest()
        assert np.array_equal(weights,np.array(old['weights_RGB'])) and indices==old['sensor_indices']
        assert pitch==old['detector']['pitch_um'] and nominal.a.shape==(103788,9)
        assert abs(nominal.singular[0]/nominal.singular[-1]-olddiagnostics['shape_only/'+exp2f.MODELS[2]]['kappa'])<1e-12
        positions=[dict(position_id='origin',axis='origin',signed_pixel=0.,dx_pixel=0.,dy_pixel=0.,sign='zero')]
        for axis in ['x','y']:
            for shift in [-.05,-.02,-.01,-.005,.005,.01,.02,.05]:
                positions.append(dict(position_id=f'{axis}_{shift:+g}',axis=axis,signed_pixel=shift,dx_pixel=shift if axis=='x' else 0.,dy_pixel=shift if axis=='y' else 0.,sign='positive' if shift>0 else 'negative'))
        for p in positions:p.update(signed_um=p['signed_pixel']*pitch,signed_nm=p['signed_pixel']*pitch*1000)
        sourcepath=ROOT/'integration/single_spiral_to_hsi/n03_exp2'
        paths=list(EXP2.rglob('*'));paths=[p for p in paths if p.is_file()]
        paths+=list(sourcepath.glob('*.py'))+list((ROOT/'integration/single_spiral_to_hsi/n03_exp1').glob('*.py'))+assets
        paths+=[ROOT/'README.md',ROOT/'integration/single_spiral_to_hsi/tests/test_n03_exp2.py']
        paths+=[ROOT/'optics/n02_single_spiral/results/n02/n02_20261019_02/B2'/n for n in ['height_um.npy','aperture_mask.npy','config.json']]
        paths+=[ROOT/'framework/DeepLensHSI/src/sensor/sensor.py']
        inputs=freeze(out,paths)
        interfaces={}
        for fn in [exp2f.load,exp2f.matrix,exp2f.Operator.solve,exp2p.detector_perturb,exp2n.gaussian_direction,exp2n.protocol_q]:
            lines,line=inspect.getsourcelines(fn);interfaces[fn.__qualname__]=dict(file=inspect.getsourcefile(fn),line=line,length=len(lines),sha256=sha(inspect.getsourcefile(fn)))
        config=dict(notice=NOTICE,branch='A_CALIBRATION',environment=environment('CPU'),git_before=before,task_source=task_source(),
                    reference=str(EXP2),wavelengths_nm=old['wavelengths_nm'],weights_RGB=weights.tolist(),sensor_indices=indices,
                    detector=old['detector'],shape_mode='shape_only',positions=positions,seeds=old['noise']['seeds'],
                    spectra_reference=dict(path=str(EXP2/'run_config.json'),sha256=sha(EXP2/'run_config.json'),key='spectra'),
                    nominal_A_sha256=nominal_hash,nominal_kappa=float(nominal.singular[0]/nominal.singular[-1]),
                    thresholds=dict(primary_NRMSE=.01,sensitivity=[.005,.02],KKT=1e-7,Q40_SNR_error_db=.3,
                                    zero_regression_estimate_max_abs=1e-12,zero_regression_NRMSE_abs=1e-12),
                    noise='EXP2 same gaussian_direction(seed,spectrum_index,size), same direction paired across all shifts; each true signal rescaled to realized Q40',
                    boundary='continuous shifted source-cell to detector overlap, zero extension; per-lambda detector shape normalized, throughput loss not retained in A',
                    normalization='shape_only；记录归一化前capture；无gain、模糊、谱依赖位移或通量修正',
                    statistics='每位置每协议18谱或54例；mean/median/P90/max、超过阈值比例、按seed均值及其样本SD；另列跨谱/样本SD；零基准只计一次',
                    interval_rule='首个离散超限邻段；不假设单调，不外推；没有超限则仅说明在已测0.05内未见超限',
                    expected_NNLS=1224,interfaces=interfaces)
        write(out/'run_config.json',config)
        textfile(out/'00_preflight.md','# A运行前审计\n\n'+NOTICE+'\n\nEXP2最终47项产物已按final_manifest只读核验；读取主体报告、补充报告、配置、9/25带诊断、metrics、input_manifest及源码快照。接口路径和具体行号见run_config.interfaces；输入SHA见input_manifest。\n\n完全复用EXP2正式连续面积积分detector_perturb，而非旧离散shift；固定A_nominal、18谱及3个原seed。17个唯一位置×18谱×4观测=1224次NNLS，预计CPU约10–30秒。原工作区dirty如实记录，无清理。\n\nshape_only会在detector裁切后归一，舍弃其通量差异；Q40只匹配全ROI实际SNR，不混用P_in。1%主阈值及0.5%/2%参考先于求解冻结，属于本实验操作性判据而非加工标准。\n')
        event(out,started,'CONTRACT_FROZEN',positions=17,expected_solves=1224,pitch_um=pitch)
        testpath=CODE.parent/'tests/test_n03_exp2b.py';spec=importlib.util.spec_from_file_location('exp2b_tests',testpath);test=importlib.util.module_from_spec(spec);spec.loader.exec_module(test)
        checks=test.a_checks(positions,nominal,exp2f.render,cube,weights)
        if any(not t['passed'] for t in checks):write(out/'tests.json',checks);raise RuntimeError('A工程基础门失败')
        shift_records=[];zero_regression=[]
        for pos in positions:
            if pos['axis']=='origin':true_a=nominal.a;capture=nominal_capture;detail=dict(method='zero reference nominal')
            else:
                spec=dict(kind='common_shift_'+pos['axis'],level=pos['signed_pixel'])
                detector,_,detail=exp2p.detector_perturb(fine[exp2f.MODELS[2]],weights,spec,pitch,edges,det_edges)
                capture=detector.sum(axis=(1,2));detector/=capture[:,None,None]
                true_a=exp2f.matrix(detector,weights)
            diff=float(np.linalg.norm(true_a-nominal.a)/np.linalg.norm(nominal.a))
            passed=(diff==0 if pos['axis']=='origin' else diff>1e-12)
            checks.append(dict(name=pos['position_id']+'/失配真实性',passed=passed,value=diff))
            if not passed:raise RuntimeError('A1失配真实性失败')
            shift_records.append(dict(**pos,relative_A_change=diff,detector_capture_before_shape_normalization=capture.tolist(),detail=detail))
            for i,case in enumerate(old['spectra']):
                truth=np.array(case['truth']);clean=true_a@truth
                for seed in [0]+old['noise']['seeds']:
                    protocol='noiseless' if seed==0 else 'Q40'
                    if seed==0:y=clean;amplitude=0.
                    else:y,amplitude=exp2n.protocol_q(clean,exp2n.gaussian_direction(seed,i,len(clean)),40)
                    estimate,residual,kkt=nominal.solve(y)
                    quality=exp2f.SOLVERS.spectral_metrics(truth,estimate,exp2f.WAVES)
                    row=dict(solution_index=len(rows),spectrum_index=i,spectrum=case['name'],kind=case['kind'],protocol=protocol,seed=seed,
                             **{k:pos[k] for k in ['position_id','axis','sign','signed_pixel','signed_um','signed_nm']},
                             dx_pixel=pos['dx_pixel'],dy_pixel=pos['dy_pixel'],NRMSE=quality['spectral_NRMSE'],SAM_deg=quality['SAM_deg'],
                             relative_amplitude_bias=quality['relative_amplitude_bias'],relative_sensor_residual=residual,
                             actual_SNR_db=exp2n.realized_snr(clean,y),noise_std=amplitude,solver_status='SUCCESS',nonnegative=bool(estimate.min()>=0),kkt=kkt,
                             relative_A_change=diff)
                    if seed and abs(row['actual_SNR_db']-40)>.3:raise RuntimeError('实际Q40不符合')
                    if not np.isfinite(row['NRMSE']) or quality['SAM_deg'] is None:raise RuntimeError('非法光谱指标')
                    rows.append(row);estimates.append(estimate)
                    if pos['axis']=='origin':
                        ref=next(r for r in oldmetrics if r['model']==exp2f.MODELS[2] and r['shape_mode']=='shape_only' and r['protocol']==('noiseless' if seed==0 else 'Q') and r['spectrum']==case['name'] and int(r['seed'])==seed and (seed==0 or float(r['target_SNR_db'])==40))
                        estdiff=float(np.max(abs(estimate-np.array(json.loads(ref['estimate'])))))
                        metricdiff=abs(row['NRMSE']-float(ref['NRMSE']))
                        zero_regression.append(dict(spectrum=case['name'],seed=seed,estimate_max_abs_difference=estdiff,NRMSE_absolute_difference=metricdiff))
                        if estdiff>1e-12 or metricdiff>1e-12:raise RuntimeError('A0零位逐例回归失败')
            if pos['axis']=='origin':
                write(out/'zero_regression.json',zero_regression);event(out,started,'A0_ZERO_REGRESSION_PASS',cases=len(zero_regression),max_estimate_error=max(x['estimate_max_abs_difference'] for x in zero_regression))
            event(out,started,'POSITION_COMPLETE',position=pos['position_id'],solves=len(rows),A_change=diff)
        assert len(rows)==1224 and len(zero_regression)==72
        assert hashlib.sha256(nominal.a.tobytes()).hexdigest()==nominal_hash
        checks.append(dict(name='1224完整且固定名义字典未变',passed=True,value=len(rows)))
        write(out/'tests.json',checks);write(out/'shift_manifest.json',shift_records)
        csvwrite(out/'metrics.csv',rows)
        with (out/'spectral_solutions.npz').open('xb') as f:np.savez_compressed(f,estimate=np.stack(estimates),truth=np.array([c['truth'] for c in old['spectra']]),spectrum_index=np.array([r['spectrum_index'] for r in rows]))
        summary=aggregate(rows);intervals=tolerance_intervals(summary)
        csvwrite(out/'tolerance_summary.csv',summary);csvwrite(out/'tolerance_intervals.csv',intervals)
        # 仅引用已归档B0/B1，无新求解；同时给均值、中位数及按谱配对胜率。
        comparisons=[]
        for protocol in ['noiseless','Q40']:
            for name in exp2f.MODELS[:2]:
                refs=[r for r in oldmetrics if r['model']==name and r['shape_mode']=='shape_only' and r['protocol']==('noiseless' if protocol=='noiseless' else 'Q') and (protocol=='noiseless' or float(r['target_SNR_db'])==40)]
                values=[float(r['NRMSE']) for r in refs]
                zero=[r for r in rows if r['position_id']=='origin' and r['protocol']==protocol]
                win=np.mean([r['NRMSE']<float(next(b for b in refs if b['spectrum']==r['spectrum'] and int(b['seed'])==r['seed'])['NRMSE']) for r in zero])
                comparisons.append(dict(protocol=protocol,control=name,control_mean_NRMSE=float(np.mean(values)),control_median_NRMSE=float(np.median(values)),B2_origin_paired_win_rate=float(win),n=len(values)))
        csvwrite(out/'archived_control_comparison.csv',comparisons)
        allsum=[r for r in summary if r['spectrum_kind']=='ALL']
        fig,axes=plt.subplots(2,2,figsize=(12,9))
        for i,axis in enumerate(['x','y']):
            for j,protocol in enumerate(['noiseless','Q40']):
                items=sorted([r for r in allsum if r['protocol']==protocol and r['axis'] in [axis,'origin']],key=lambda r:r['signed_pixel'])
                for stat in ['mean','median','p90','max']:axes[i,j].semilogy([r['signed_pixel'] for r in items],[max(r['NRMSE_'+stat],1e-16) for r in items],'-o',label=stat,ms=3)
                axes[i,j].axhline(.01,color='k',ls=':',label='1% operational threshold');axes[i,j].set(title=axis+'/'+protocol,xlabel='Signed shift (pixel)',ylabel='Spectral NRMSE');axes[i,j].legend(fontsize=7);axes[i,j].grid(alpha=.2)
        plot_finish(fig,out/'figures/nrmse_signed_shift.png','Position calibration tolerance: mean / median / P90 / worst',pitch)
        fig,axes=plt.subplots(1,2,figsize=(12,5))
        for ax,axis in zip(axes,['x','y']):
            for protocol in ['noiseless','Q40']:
                items=sorted([r for r in allsum if r['protocol']==protocol and r['axis'] in [axis,'origin']],key=lambda r:r['signed_pixel'])
                ax.plot([r['signed_pixel'] for r in items],[r['fraction_NRMSE_gt_0.01'] for r in items],'-o',label=protocol)
            ax.set(title=axis,xlabel='Signed shift (pixel)',ylabel='Fraction with NRMSE > 1%');ax.grid(alpha=.2);ax.legend()
        plot_finish(fig,out/'figures/fraction_exceeding_threshold.png','1% threshold exceedance; zero baseline counted once in statistics',pitch)
        fig,axes=plt.subplots(1,2,figsize=(11,5))
        for ax,protocol in zip(axes,['noiseless','Q40']):
            worst=max((r for r in rows if r['protocol']==protocol),key=lambda r:r['NRMSE'])
            ax.plot(exp2f.WAVES,old['spectra'][worst['spectrum_index']]['truth'],'k-o',label='GT')
            ax.plot(exp2f.WAVES,estimates[worst['solution_index']],'--o',label='NNLS fixed nominal')
            ax.set(title=f'{protocol}: {worst["position_id"]}, {worst["spectrum"]}\nseed={worst["seed"]}, NRMSE={worst["NRMSE"]:.5g}',xlabel='Wavelength (nm)',ylabel='Band-integrated energy');ax.legend();ax.grid(alpha=.2)
        plot_finish(fig,out/'figures/worst_spectra.png','Worst cases from all pre-registered positions; no oracle reconstruction',pitch)
        report=['# A：9带位置标定容差','',NOTICE,'',
                '**工程PASS；1224例全部完成。原N03 G0和N02 G2/G3失败状态不变。**','',
                f'完全复用EXP2正式连续源像元→detector积分、pitch={pitch:.15g}um、186² detector、shape_only及物理RGB。A_nominal冻结，仅A_true平移，沿用零延拓及detector裁切后逐带归一。因此本实验不保留截取通量差，不是DOE加工纳米公差。',
                '17个位置含唯一零基准，18条原谱、无噪声和原3seed Q40；Q40逐模型true signal匹配实际40dB，同谱/同seed标准高斯方向在全部δ间配对。没有P_in混合，没有oracle、未知位置搜索或重新标定。',
                f'A0零位72例逐例复现EXP2，最大估计绝对差{max(x["estimate_max_abs_difference"] for x in zero_regression):.6g}。非零位矩阵差及归一化前capture见shift_manifest；KKT/残差/非负性/实际SNR见metrics。',
                f'1 pixel={pitch:.12f}um={pitch*1000:.9f}nm；0.005/0.01/0.02/0.05 pixel分别为{[round(x*pitch*1000,6) for x in [.005,.01,.02,.05]]}nm。','',
                '## 预注册1%参考容差：首次离散超限区间','',
                '|协议|轴|方向|统计量|首次超限绝对pixel区间|对应绝对nm区间|说明|','|---|---|---|---|---|---|---|']
        for r in intervals:
            if r['threshold']==.01:
                report.append(f'|{r["protocol"]}|{r["axis"]}|{r["sign"]}|{r["statistic"]}|({r["lower_abs_pixel"]},{r["upper_abs_pixel"]})|({r["lower_abs_nm"]:.6g},{r["upper_abs_nm"]})|{r["status"]}|')
        report+=['','None表示在已扫描最大0.05pixel仍未发现超限，不是可外推的物理上限；区间只给相邻离散位置。未强制误差单调，完整序列及monotonic标记见tolerance_intervals.csv。0.5%/2%敏感性同表保留，未事后选择通过阈值。','',
                 '## 全谱统计与最坏谱','',
                 '|位置|协议|均值|中位数|P90|最坏|超过1%比例|seed均值SD|最坏谱|','|---|---|---:|---:|---:|---:|---:|---:|---|']
        for r in allsum:report.append(f'|{r["position_id"]}|{r["protocol"]}|{r["NRMSE_mean"]:.6g}|{r["NRMSE_median"]:.6g}|{r["NRMSE_p90"]:.6g}|{r["NRMSE_max"]:.6g}|{r["fraction_NRMSE_gt_0.01"]:.6g}|{r["NRMSE_seed_mean_sd"]:.3g}|{r["worst_spectrum"]}|')
        report+=['','按onehot/double/broad/random分组的同口径表，以及SAM、相对总能量偏差、传感器相对残差，见tolerance_summary.csv；每个位置无噪声18例、Q40为54例。跨样本SD与3个seed均值之间的样本SD分别保存，3seed不解释为精确置信区间。',
                 'NRMSE=||estimate-truth||₂/||truth||₂；SAM为向量夹角度。传感器残差不能替代谱误差。旧B0/B1只读配对参考见archived_control_comparison.csv，分别报告均值、中位数与B2零位逐谱胜率，不把秩3控制的低中位数当可恢复性门槛。','',
                 f'测试{len(checks)}项通过、失败0；全部求解KKT≤{max(r["kkt"] for r in rows):.6g}，失败率0。真谱仅在合成/评价出现；真实恢复接口只有A_nominal和y。',
                 '图：figures/nrmse_signed_shift.png、fraction_exceeding_threshold.png、worst_spectra.png。估计曲线按metrics.solution_index索引spectral_solutions.npz，真谱指向旧EXP2配置并保存18×9的小数组，不复制大型图像。',
                 '结论仅限归档PSF的点源位置标定敏感性；方向/正负号差异按实测表保留。达到扫描上界未超限不等于任何更大位移可用，也不等于DOE器件纳米级加工合格。B支路独立验收，不与本支路合并宣称物理认证。']
        textfile(out/'result_summary.md','\n'.join(report)+'\n')
        textfile(out/'DELIVERY.md','# A正式入口\n\n'+NOTICE+'\n\n工程PASS，1224例完成；阅读[result_summary.md](result_summary.md)、[tolerance_intervals.csv](tolerance_intervals.csv)、[tolerance_summary.csv](tolerance_summary.csv)。原始逐例metrics和曲线索引均归档；不扩展其他实验。\n')
        write(out/'qa.json',dict(status='PASS',solves=len(rows),unique_positions=17,zero_regression_cases=72,
                                  max_zero_estimate_error=max(x['estimate_max_abs_difference'] for x in zero_regression),
                                  checks_passed=len(checks),solver_failures=0,max_kkt=max(r['kkt'] for r in rows),
                                  max_Q40_SNR_error_db=max(abs(r['actual_SNR_db']-40) for r in rows if r['protocol']=='Q40')))
        finish(out,started,'A_ENGINEERING_PASS',before,inputs,solves=len(rows),tests=len(checks))
    except Exception:
        textfile(out/'logs/failure.txt',traceback.format_exc())
        if rows:csvwrite(out/'partial_metrics.csv',rows)
        event(out,started,'FAILED_STOP',error=traceback.format_exc().splitlines()[-1]);raise


if __name__=='__main__':main()
