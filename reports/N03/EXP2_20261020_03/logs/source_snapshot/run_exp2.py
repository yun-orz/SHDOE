"""EXP2入口：严格按preflight→实现门→pilot→full→25带诊断执行。"""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
import scipy
import matplotlib
import torch

from sampling import centered_grid,rebin_cube
from forward import ROOT,WAVES,MODELS,load,detector_models,matrix,render,Operator,diagnostic,SOLVERS
from perturbations import definitions,perturb,detector_perturb
from noise import gaussian_direction,protocol_q,protocol_p,realized_snr
from analysis import save_csv,summarize,publish,NOTICE


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();root=ROOT
    if out.exists():raise FileExistsError(f'拒绝覆盖旧输出：{out}')
    if out.parent!=root/'reports/N03' or not out.name.startswith('EXP2_'):
        raise ValueError('输出必须为reports/N03/EXP2_<unique_run_id>')
    out.mkdir(parents=True,exist_ok=False);(out/'logs').mkdir();(out/'figures').mkdir()
    started=time.perf_counter()
    def event(stage,**kw):
        record=dict(seconds=time.perf_counter()-started,stage=stage,**kw)
        with (out/'logs/events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
        print(json.dumps(record,ensure_ascii=False),flush=True)
    try:
        git=lambda *parts:subprocess.check_output(['git','-C',str(root),*parts],encoding='utf-8').strip()
        git_before=dict(head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),dirty=git('status','--short','--untracked-files=all'),tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(root),'diff','--binary'])).hexdigest())
        archive=root/'reports/N03/EXP1_verified'
        old=json.loads((archive/'run_config.json').read_text(encoding='utf-8'))
        olddiag=json.loads((archive/'matrix_diagnostics.json').read_text(encoding='utf-8'))
        oldsummary=json.loads((archive/'summary_metrics.json').read_text(encoding='utf-8'))
        oldrun=json.loads((archive/'logs/run_record.json').read_text(encoding='utf-8'))
        oldartifact=json.loads((archive/'artifact_manifest.json').read_text(encoding='utf-8'))
        bad=[p for p,h in oldartifact.items() if sha(archive/p)!=h]
        if bad:raise RuntimeError(f'G-impl STOP: EXP1归档哈希不一致：{bad}')
        # 保护全部先前N03报告、EXP1代码、用户README及本轮实际光学输入。
        protected=[p for p in (root/'reports/N03').rglob('*') if p.is_file() and out not in p.parents]
        protected+=list((root/'integration/single_spiral_to_hsi/n03_exp1').glob('*.py'))
        protected+=[root/'README.md',root/'integration/single_spiral_to_hsi/tests/test_n03_exp1.py']
        base=root/'optics/n02_single_spiral/results/n02/n02_20261019_02/B2'
        protected+=list((base/'cases').glob('*.npz'))
        protected+=[base/p for p in ['height_um.npy','aperture_mask.npy','config.json','frozen_sha256.json']]
        protected+=[root/'optics/n02_single_spiral/results/n02/n02_20261019_02/gates.json',
                    root/'optics/n02_single_spiral/reports/n02_1c_r2/n02_1cr2_20261020_02/N02_1CR2_final_audit.md',
                    root/'framework/DeepLensHSI/src/sensor/sensor.py',root/'framework/DeepLensHSI/5_eval_pretrained.py']
        source=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).parent.parent/'tests/test_n03_exp2.py']
        fine,weights,asset_paths,records,indices,pitch=load(root)
        frozen=json.loads((base/'frozen_sha256.json').read_text(encoding='utf-8'))
        for p in asset_paths[:-1]+[base/'height_um.npy',base/'aperture_mask.npy']:
            if sha(p)!=frozen[str(p.relative_to(base))]:raise RuntimeError(f'固定资产哈希不同：{p}')
        if not np.array_equal(weights,np.array(old['weights_RGB'])) or indices!=old['sensor_indices_zero_based']:
            raise RuntimeError('EXP1物理响应或波长索引不一致')
        if sha(base/'height_um.npy')!='8166b58c358b3be2862cd9401f17b6bdd6ad5dcc575e5278aaa135f28b5ba19f':raise RuntimeError('高度哈希不一致')
        for r in records:
            if abs(r['raw_energy']-1)>1e-10 or abs(r['crop_energy']/r['raw_energy']-r['crop_fraction'])>1e-12:
                raise RuntimeError('跨波长入瞳或裁切能量定义不一致')
        input_paths=list(dict.fromkeys(protected+asset_paths+source))
        input_manifest={str(p.relative_to(root)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in input_paths}
        dump(out/'input_manifest.json',input_manifest)
        # 每个被读取的源文件真正读取字节并哈希；配置不是从旧报告猜接口。
        old_source_audit={str(p.relative_to(root)):dict(lines=len(p.read_text(encoding='utf-8').splitlines()),sha256=sha(p)) for p in protected if p.suffix=='.py'}
        fine_edges,det_edges,overlap=centered_grid(512,pitch);m=len(det_edges)-1
        rebinned={name:rebin_cube(cube,overlap) for name,cube in fine.items()}
        detector_fraction=rebinned[MODELS[2]].sum(axis=(1,2))
        crop=np.array([r['crop_fraction'] for r in records]);q_shared=crop*detector_fraction
        cubes=detector_models(rebinned,q_shared)
        sensor=json.loads(asset_paths[-1].read_text(encoding='utf-8'))
        fullresponse=np.array([sensor[c+'_response'] for c in ['red','green','blue']])/sum(sensor['green_response'])
        electron_scale=float(1/np.max(fullresponse.sum(axis=0)))
        spectra=old['spectra'];seeds=[20261021,20261022,20261023]
        pilot_names=['onehot_420','onehot_600','near_equal','far_half','broad_510','random_0']
        specs=definitions();pilot_specs=[next(d for d in specs if d['id']==name) for name in ['shift_x_+0.1','chromatic_0.1','blur_0.1','gain_+0.01']]
        task_path=Path('C:/Users/李咏晨/Downloads/N03-A-EXP2_%E5%8D%95%E5%AD%94%E5%BE%84DOE%E9%B2%81%E6%A3%92%E6%80%A7%E4%B8%8E%E7%89%A9%E7%90%86%E9%87%87%E6%A0%B7%E9%AA%8C%E8%AF%81_Codex%E4%BB%BB%E5%8A%A1%E4%B9%A6.md')
        config=dict(notice=NOTICE,created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    original_gates=dict(N03_G0='FAIL_UNCHANGED',N02_G2='FAIL_UNCHANGED',N02_G3_Numerics='FAIL_UNCHANGED'),
                    git_before=git_before,wavelengths_nm=WAVES.tolist(),sensor_indices=indices,weights_RGB=weights.tolist(),
                    spectrum_unit='每离散带积分入射比例，sum=1；不乘Delta-lambda',spectra=spectra,
                    detector=dict(pitch_um=pitch,source=str(asset_paths[-1].relative_to(root)),
                                  pitch_rule='size[0]mm*1000/res[0]; y方向一致',count=m,shape=[m,m],
                                  fine_edges_um=[float(fine_edges[0]),float(fine_edges[-1])],edges_um=det_edges.tolist(),
                                  optical_axis_um=[0,0],fine_centers_rule='index-255.5',delta='四格中心各0.25；detector光轴同样四格交点',
                                  area_model='原1um像元内均匀能量的精确几何面积重叠，不是新传播认证'),
                    modes=['shape_only','throughput_aware'],q_shared=q_shared.tolist(),
                    q_definition='B2 crop_fraction(ROI/有限传播域) * detector_capture_fraction(归一ROI内)；对三模型统一只乘一次',
                    noise=dict(seeds=seeds,P_in=[1e4,1e5],read_sigma_e=[1,3],electron_scale=electron_scale,
                               electron_scale_rule='1/max_l sum_c w_c,l over original 31 points; idealized conversion, not measured QE',
                               Q_target_db=[30,40],P_assumptions='independent ideal RGB planes, no Bayer/background/dark/saturation/ADC; Gaussian read noise may yield negative observations',
                               pairing='同谱/种子Gaussian方向共用；P同种子Poisson生成方案+独立共用read方向，不宣称不同rate生成同计数'),
                    perturbations=specs,mismatch_mode='shape_only B2; M1 nominal, M2 oracle; noiseless + Q40/3 seeds',
                    perturbation_boundary='nonperiodic zero extension; unknown original outside ROI treated zero; losses recorded before shape normalization',
                    pilot=dict(spectra=pilot_names,seeds=seeds,perturbations=[s['id'] for s in pilot_specs],
                               noise_P=dict(P_in=1e4,read_sigma_e=1),noise_Q=[30],mode='shape_only'),
                    full_design='18 spectra; sampling noiseless both modes; P 2 budgets x 2 read levels; Q 30/40; 23 true-only mismatch conditions each M1/M2 noiseless+Q40. Independent single-factor groups, no Cartesian noise-by-mismatch scan',
                    nnls_numerics='SVD压缩后零行补至L+1行；补零严格不改变目标。避免SciPy 1.15.3欠定m<n路径错误终止；每例独立KKT及真实残差验证',
                    prior_failed_run='EXP2_20261020_01：G-impl通过后pilot KKT失败，未进入full；在B0秩亏压缩矩阵重现后补零行修复，保留原错误日志',
                    sampling_refinement='EXP2_20261020_02已完成，但其0.1pixel Gaussian使用fine格点采样核会低估亚像元模糊；本run改为连续高斯源/接收像元双积分，平移也直接积分到detector。保留旧run不覆盖，结论采用本run',
                    diagnostic_25band='only after core full; no spectral recovery',
                    environment=dict(executable=sys.executable,python=sys.version,numpy=np.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,torch=torch.__version__,
                                     device='CPU',precision='float64',platform=platform.platform(),threads={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']}),
                    task_source=dict(path=str(task_path),sha256=sha(task_path)),source_read_audit=old_source_audit)
        dump(out/'run_config.json',config)
        preflight=(f'从传感器JSON的12.34mm/4504像元得到pitch={pitch:.12f}um，运行时M=floor(512/pitch)={m}；矩阵应为{3*m*m}×9。'
                   f'detector边界[{det_edges[0]:.12f},{det_edges[-1]:.12f}]um，fine边界[-256,256]um，光轴均为(0,0)。'
                   'EXP1已读run_config/matrix_diagnostics/summary_metrics/run_record及源代码，全部归档产物哈希一致；RGB严格沿用索引[2,5,8,11,14,17,20,23,26]，不交换R/B。'
                   f'EXP1记录378次求解、耗时{oldrun["seconds"]:.3f}s；本轮将复核S0条件数。'
                   '原采样为1um ROI质量；本轮粗像元作面积积分。crop_fraction为有限传播域参考ROI份额，raw_energy在各波长约1；它不是材料绝对透射率或实测QE。'
                   f'协议P的全局模拟电子缩放K={electron_scale:.12g}，原始完整31点表确定，所有模型不变。模拟预算及读噪声明为情景假设。'
                   '原N03 G0 FAIL、N02 G2/G3 FAIL保留；工程检查不能替代物理数值认证。')
        (out/'00_preflight.md').write_text('# EXP2-0 输入及契约\n\n'+NOTICE+'\n\n'+preflight+'\n\nGit/dirty、实际路径、源代码/输入SHA与版本见run_config.json、input_manifest.json。\n',encoding='utf-8')
        event('PREFLIGHT_FROZEN',pitch_um=pitch,detector_count=m,spectra=len(spectra),perturbations=len(specs))
        energy=[];throughput=[]
        for name,h in fine.items():
            for band,wave in enumerate(WAVES):
                before=float(h[band].sum());inside=float(rebinned[name][band].sum());outside=before-inside
                if outside < -1e-10 or not np.isfinite(inside):raise RuntimeError('G-impl面积损失非法')
                energy.append(dict(model=name,wavelength_nm=wave,fine_sum=before,detector_sum=inside,outside_detector=outside,
                                   conservation_error=abs(inside+outside-before),q_sensor_crop=inside/before,
                                   assigned_shared_q=float(q_shared[band])))
                throughput.append(dict(model=name,wavelength_nm=wave,shape_detector_sum=float(cubes[('shape_only',name)][band].sum()),
                                       throughput_detector_sum=float(cubes[('throughput_aware',name)][band].sum()),
                                       B2_crop_fraction=float(crop[band]),B2_detector_capture=float(detector_fraction[band]),q_shared=float(q_shared[band]),
                                       reference='ROI / finite ASM domain; not absolute optical throughput'))
        save_csv(out/'sampling_energy_check.csv',energy);save_csv(out/'throughput_analysis.csv',throughput)
        ops={key:Operator(matrix(cube,weights)) for key,cube in cubes.items()}
        native=Operator(matrix(fine[MODELS[2]],weights));diags={'S0_native_B2':diagnostic(native)}
        for key,op in ops.items():diags['/'.join(key)]=diagnostic(op)
        if abs(native.singular[0]/native.singular[-1]-olddiag[MODELS[2]]['kappa'])>1e-10:
            raise RuntimeError('G-impl S0不复现EXP1')
        dump(out/'matrices_9band.json',diags)
        test_path=Path(__file__).parent.parent/'tests/test_n03_exp2.py'
        spec=importlib.util.spec_from_file_location('exp2_test',test_path);testing=importlib.util.module_from_spec(spec);spec.loader.exec_module(testing)
        checks=testing.validate(root,ops,cubes,weights,overlap,pitch,indices,electron_scale)
        checks.append(dict(name='S0对齐EXP1',passed=True,value=diags['S0_native_B2']['kappa']))
        # 逐波长直接从raw_roi与面积积分构造通量，独立核验归一化与q仅乘一次。
        for band,path in enumerate(asset_paths[:-1]):
            with np.load(path,allow_pickle=False) as z:
                raw=z['raw_roi'];r=json.loads(z['record_json'].item())
                raw_detector=rebin_cube(raw[None],overlap)[0]/r['raw_energy']
                err=float(np.max(abs(raw_detector-cubes[('throughput_aware',MODELS[2])][band])))
                checks.append(dict(name=f'通量仅一次_{WAVES[band]:g}',passed=err<1e-12,value=err))
        dump(out/'tests.json',checks)
        if any(not c['passed'] for c in checks):raise RuntimeError('G-impl失败；停止pilot/full')
        event('G_IMPL_PASS',checks=len(checks),S0_kappa=diags['S0_native_B2']['kappa'],S1_kappa=diags['shape_only/'+MODELS[2]]['kappa'])
        # 释放native完整U/A，后续只保留S0诊断及需要的detector算子。
        native_for_check=native
        rows=[];perturbation_manifest=[];mismatch_checks=[]
        def recover(case_index,phase,key,recon_op,true_op,y,clean,protocol,seed=0,reconstruction='M0_matched',spec=None,meta=None,target=None,pin=None,read=None,grid=None):
            case=spectra[case_index];truth=np.array(case['truth']);estimate,residual,kkt=recon_op.solve(y)
            metric=SOLVERS.spectral_metrics(truth,estimate,WAVES)
            peaks=np.flatnonzero(np.isclose(truth,truth.max(),rtol=0,atol=1e-15))
            peakerr=float(np.min(abs(WAVES[np.argmax(estimate)]-WAVES[peaks])))
            mode,name=key;sp=spec or dict(kind='none',level=0,id='none')
            row=dict(sample_id=f'{phase}_{len(rows):06d}',phase=phase,spectrum=case['name'],kind=case['kind'],seed=seed,model=name,
                     protocol=protocol,reconstruction=reconstruction,perturbation_type=sp['kind'],perturbation_level=sp['level'],perturbation_id=sp['id'],
                     grid_pitch_um=pitch if grid is None else grid,shape_mode=mode,NRMSE=metric['spectral_NRMSE'],SAM_deg=metric['SAM_deg'],
                     amplitude_bias=metric['amplitude_bias'],relative_amplitude_bias=metric['relative_amplitude_bias'],
                     relative_sensor_residual=residual,peak_error_nm=peakerr,actual_SNR_db=realized_snr(clean,y),
                     solver_status='SUCCESS',kkt_violation=kkt,zero_estimate=bool(np.linalg.norm(estimate)<1e-15),
                     signal_sum=float(clean.sum()),signal_l2=float(np.linalg.norm(clean)),observation_sum=float(y.sum()),
                     noise_l2=float(np.linalg.norm(y-clean)),P_in=pin,read_sigma_e=read,target_SNR_db=target,
                     expected_electrons=None,realized_poisson_electrons=None,noise_std=None,
                     truth=truth.tolist(),estimate=estimate.tolist())
            if meta:row.update(meta)
            if protocol in ['Q','mismatch_Q40'] and abs(row['actual_SNR_db']-target)>.3:raise RuntimeError('G-full Q SNR不匹配')
            if not all(np.isfinite(row[k]) for k in ['NRMSE','amplitude_bias','relative_sensor_residual','signal_l2']):raise RuntimeError('非有限指标')
            rows.append(row)
        def matched_batch(phase,selected,modes,ps,qs):
            for mode in modes:
                for name in MODELS:
                    key=(mode,name);op=ops[key]
                    for i in selected:
                        s=np.array(spectra[i]['truth']);clean=op.a@s
                        recover(i,phase,key,op,op,clean,clean,'noiseless')
                        for seed in seeds:
                            direction=gaussian_direction(seed,i,len(clean))
                            for target in qs:
                                y,amp=protocol_q(clean,direction,target)
                                recover(i,phase,key,op,op,y,clean,'Q',seed,target=target,meta=dict(noise_std=amp))
                            for pin,read in ps:
                                y,meta=protocol_p(clean,pin,electron_scale,read,seed,i)
                                recover(i,phase,key,op,op,y,clean,'P',seed,meta=meta,pin=pin,read=read)
        def mismatch_batch(phase,selected,scenarios):
            key=('shape_only',MODELS[2]);assumed=ops[key];original=fine[MODELS[2]]
            for scenario in scenarios:
                coarse,changed_weights,detail=detector_perturb(original,weights,scenario,pitch,fine_edges,det_edges)
                capture=coarse.sum(axis=(1,2));coarse/=capture[:,None,None]
                true=Operator(matrix(coarse,changed_weights))
                diff=float(np.linalg.norm(true.a-assumed.a)/np.linalg.norm(assumed.a))
                if diff<=1e-12:raise RuntimeError(f'失配未真正改变A_true: {scenario}')
                perturbation_manifest.append(dict(phase=phase,**scenario,details=detail,detector_pre_normalization_capture=capture.tolist(),relative_A_change=diff,
                                                   A_recon='fixed nominal shape_only B2',true_rank=true.rank,true_kappa=float(true.singular[0]/true.singular[-1])))
                mismatch_checks.append(dict(name=f'{phase}/{scenario["id"]}/true_only',passed=diff>1e-12,value=diff))
                for i in selected:
                    truth=np.array(spectra[i]['truth']);clean=true.a@truth
                    for reconstruction,recon in [('M1_nominal',assumed),('M2_oracle',true)]:
                        recover(i,phase,key,recon,true,clean,clean,'mismatch_noiseless',reconstruction=reconstruction,spec=scenario,meta=dict(relative_A_change=diff))
                    for seed in seeds:
                        direction=gaussian_direction(seed,i,len(clean));y,amp=protocol_q(clean,direction,40)
                        for reconstruction,recon in [('M1_nominal',assumed),('M2_oracle',true)]:
                            recover(i,phase,key,recon,true,y,clean,'mismatch_Q40',seed,reconstruction,scenario,
                                    meta=dict(relative_A_change=diff,noise_std=amp),target=40)
                event('MISMATCH_GROUP_COMPLETE',phase=phase,condition=scenario['id'],A_relative_change=diff,solves=len(rows))
        pilot_selected=[i for i,s in enumerate(spectra) if s['name'] in pilot_names]
        matched_batch('pilot',pilot_selected,['shape_only'],[(1e4,1)],[30])
        mismatch_batch('pilot',pilot_selected,pilot_specs)
        pilot_rows=[r for r in rows if r['phase']=='pilot']
        if len(pilot_selected)!=6 or any(r['solver_status']!='SUCCESS' for r in pilot_rows):raise RuntimeError('G-pilot失败')
        save_csv(out/'pilot_metrics.csv',pilot_rows)
        dump(out/'pilot_gate.json',dict(status='PASS',spectra=pilot_names,seeds=seeds,solves=len(pilot_rows),failure_count=0,
                                       scientific_bad_results='不会因高误差停止；实现正确则记录负结果'))
        event('G_PILOT_PASS',solves=len(pilot_rows))
        selected=list(range(18))
        matched_batch('full',selected,['shape_only','throughput_aware'],[(pin,read) for pin in [1e4,1e5] for read in [1,3]],[30,40])
        # S0只做B2无噪声校对，不重跑EXP1噪声或扩大波段。
        for i in selected:
            clean=native_for_check.a@np.array(spectra[i]['truth'])
            recover(i,'full',('shape_only',MODELS[2]),native_for_check,native_for_check,clean,clean,'S0_native_noiseless',grid=1.)
        event('FULL_SAMPLING_NOISE_COMPLETE',solves=len(rows))
        mismatch_batch('full',selected,specs)
        fullrows=[r for r in rows if r['phase']=='full']
        # 全体P的相同入射量、同模式探测总量核验；Q所有行已在recover内检查实际SNR。
        fairness=[]
        for mode in ['shape_only','throughput_aware']:
            for i in selected:
                truth=np.array(spectra[i]['truth'])
                totals=[float((ops[(mode,name)].a@truth).sum()) for name in MODELS]
                err=(max(totals)-min(totals))/max(totals)
                fairness.append(dict(name=f'P共享总量_{mode}_{i}',passed=err<1e-12,value=err))
        if any(not c['passed'] for c in fairness):raise RuntimeError('G-full P预算不公平')
        dump(out/'postrun_checks.json',mismatch_checks+fairness)
        event('G_FULL_PASS',solves=len(fullrows),postrun_checks=len(mismatch_checks+fairness))
        # 所有核心9带完成后，仅对原生25标准波长构造测量矩阵；绝不调用solve。
        wave25=np.arange(420,661,10);h25=[]
        for wave in wave25:
            path=base/'cases'/f'{wave:g}nm.npz'
            if sha(path)!=frozen[str(path.relative_to(base))]:raise RuntimeError('25带输入哈希失败')
            with np.load(path,allow_pickle=False) as z:
                rec=json.loads(z['record_json'].item());h=z['normalized_psf']
                if rec['wavelength_nm']!=wave or h.shape!=(512,512) or not np.isfinite(h).all() or h.min()<0:raise RuntimeError('25带资产非法')
                coarse=rebin_cube(h[None],overlap)[0];h25.append(coarse/coarse.sum())
        weights25=fullresponse[:,2:27]
        a25=matrix(np.stack(h25),weights25);op25=Operator(a25);diag25=diagnostic(op25)
        diag25.update(wavelengths_nm=wave25.tolist(),scope='NO_RECONSTRUCTION',notice=NOTICE)
        dump(out/'matrices_25band_diagnostic.json',diag25)
        event('G_25DIAG_COMPLETE',rank=diag25['rank'],kappa=diag25['kappa'],no_reconstruction=True)
        summary=summarize(rows)
        save_csv(out/'metrics.csv',fullrows);save_csv(out/'summary_metrics.csv',summary)
        save_csv(out/'model_mismatch.csv',[r for r in fullrows if r['protocol'].startswith('mismatch')])
        save_csv(out/'noise_calibration.csv',[r for r in fullrows if r['protocol'] in ['P','Q']])
        dump(out/'perturbation_manifest.json',perturbation_manifest)
        dump(out/'spectral_solutions.json',fullrows)
        ratios=[]
        for r in fullrows:
            if r['protocol']!='mismatch_Q40' or r['reconstruction']!='M1_nominal':continue
            baseline=next(b for b in fullrows if b['protocol']=='Q' and b['model']==MODELS[2] and b['shape_mode']=='shape_only' and b['target_SNR_db']==40 and b['spectrum']==r['spectrum'] and b['seed']==r['seed'])
            ratios.append(dict(spectrum=r['spectrum'],seed=r['seed'],perturbation_id=r['perturbation_id'],
                               M0_NRMSE=baseline['NRMSE'],M1_NRMSE=r['NRMSE'],
                               error_ratio=r['NRMSE']/baseline['NRMSE'] if baseline['NRMSE']>1e-12 else None,
                               error_difference=r['NRMSE']-baseline['NRMSE']))
        save_csv(out/'mismatch_ratios.csv',ratios)
        publish(out,rows,summary,diags,diag25,energy,checks,config,preflight,cubes[('shape_only',MODELS[2])][4],fine[MODELS[2]][4],perturbation_manifest)
        changed=[p for p,h in input_manifest.items() if sha(root/p)!=h['sha256']]
        diff_after=hashlib.sha256(subprocess.check_output(['git','-C',str(root),'diff','--binary'])).hexdigest()
        if changed or diff_after!=git_before['tracked_diff_sha256']:raise RuntimeError(f'旧文件保护失败：{changed}')
        dump(out/'preservation.json',dict(status='PASS',checked_files=len(input_manifest),changed_inputs=changed,tracked_diff_unchanged=True))
        command=subprocess.list2cmdline([sys.executable,'-B',*sys.argv])
        replay=f"& '{sys.executable}' -B E:\\SH\\integration\\single_spiral_to_hsi\\n03_exp2\\run_exp2.py --output E:\\SH\\reports\\N03\\EXP2_replay_unique"
        (out/'run_commands.md').write_text('# EXP2运行命令\n\n'+NOTICE+'\n\n实际命令：\n\n```powershell\n'+command+'\n```\n\n复跑，必须新输出目录：\n\n```powershell\n$env:OMP_NUM_THREADS=\'4\'\n$env:MKL_NUM_THREADS=\'4\'\n$env:OPENBLAS_NUM_THREADS=\'4\'\n$env:PYTHONIOENCODING=\'utf-8\'\n$env:PYTHONDONTWRITEBYTECODE=\'1\'\n'+replay+'\n```\n\nCPU，float64，既有环境，不安装依赖。完整实验先过G-impl及6谱pilot，才运行18谱full；25带只诊断。\n',encoding='utf-8')
        record=dict(status='COMPLETE_EXP2_ONLY',gates=dict(G_impl='PASS',G_pilot='PASS',G_full='PASS',G_25diag='PASS_NO_RECONSTRUCTION'),
                    original_gates=config['original_gates'],seconds=time.perf_counter()-started,command=command,
                    engineering_checks=len(checks),engineering_failures=0,postrun_checks=len(mismatch_checks+fairness),
                    pilot_solves=len(pilot_rows),full_solves=len(fullrows),seed_count=len(seeds),preservation='PASS',
                    solver_failures=0,git_after=git('status','--short','--untracked-files=all'))
        dump(out/'logs/run_record.json',record)
        event('DELIVERED',seconds_total=time.perf_counter()-started,full_solves=len(fullrows),next_stage='STOP_FOR_REVIEW')
        dump(out/'artifact_manifest.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
    except Exception:
        (out/'logs/failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        event('FAILED_STOP',error=traceback.format_exc().splitlines()[-1])
        raise


if __name__=='__main__':main()
