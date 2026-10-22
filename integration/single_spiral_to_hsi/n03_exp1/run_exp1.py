"""EXP1受限探索入口：预注册、工程门、三组对照、图表和可复现归档。"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import scipy
import torch

from forward import WAVELENGTHS, MODELS, load_assets, point_matrix, render_multiband
from solvers import factorize, solve_nnls, spectral_metrics

NOTICE = 'EXPLORATORY ONLY — archived B2 PSF numerical-convergence certification is incomplete; results do not establish physical DOE performance.'


def dump(path, value):
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def library():
    spectra = []
    def add(name, kind, values):
        arr=np.asarray(values,dtype=float); arr/=arr.sum()
        spectra.append(dict(name=name,kind=kind,truth=arr.tolist()))
    for i,wave in enumerate(WAVELENGTHS):
        add(f'onehot_{wave:g}','onehot',np.eye(9)[i])
    for name,i,j,ratio in [('near_equal',3,4,1),('near_half',5,6,.5),('far_equal',0,8,1),('far_half',1,7,.5)]:
        a=np.zeros(9);a[i]=1;a[j]=ratio;add(name,'double',a)
    for name,center,width in [('broad_510',510,45),('broad_585',585,60)]:
        add(name,'broad',np.exp(-.5*((WAVELENGTHS-center)/width)**2))
    rng=np.random.default_rng(20261020)
    for i in range(3):add(f'random_{i}','random',rng.uniform(0,1,9))
    return spectra


def figure_finish(fig,path,title):
    fig.suptitle(title+'\n9 bands: 420,450,480,510,540,570,600,630,660 nm; shape_only; native 1 um grid',fontsize=10)
    fig.text(.5,.015,NOTICE.replace('; results',';\nresults'),ha='center',fontsize=7)
    fig.tight_layout(rect=(0,.08,1,.90));fig.savefig(path,dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[3];out=args.output.resolve()
    if out.exists():raise FileExistsError(f'拒绝覆盖已有目录：{out}')
    out.mkdir(parents=True,exist_ok=False);(out/'logs').mkdir();(out/'figures').mkdir()
    start=time.perf_counter();log=[]
    def event(stage,**kw):
        record=dict(seconds=time.perf_counter()-start,stage=stage,**kw)
        log.append(record);print(json.dumps(record,ensure_ascii=False),flush=True)
        with (out/'logs/events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    try:
        git=lambda *parts:subprocess.check_output(['git','-C',str(root),*parts],encoding='utf-8').strip()
        git_before=dict(head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),dirty=git('status','--short','--untracked-files=all'))
        # 同时保护用户已修改的README和先前未提交的N03产物。
        previous=[p for p in (root/'reports/N03').rglob('*') if p.is_file() and out not in p.parents]
        references=[root/'README.md',root/'integration/single_spiral_to_hsi/n03_audit.py',root/'integration/single_spiral_to_hsi/INTERFACE_PLAN.md',
                    root/'optics/n02_single_spiral/results/n02/n02_20261019_02/gates.json',
                    root/'optics/n02_single_spiral/results/n02/n02_20261019_02/B2/height_um.npy',
                    root/'optics/n02_single_spiral/results/n02/n02_20261019_02/B2/aperture_mask.npy',
                    root/'optics/n02_single_spiral/results/n02/n02_20261019_02/B2/frozen_sha256.json',
                    root/'optics/n02_single_spiral/results/n02/n02_20261019_02/B2/config.json',
                    root/'optics/n02_single_spiral/reports/n02_1c_r2/n02_1cr2_20261020_02/N02_1CR2_final_audit.md']
        references += [root/'framework/DeepLensHSI'/p for p in ['src/sensor/sensor.py','src/hsi_camera.py','src/deeplens/render_psf.py','5_eval_pretrained.py']]
        source=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).parent.parent/'tests/test_n03_exp1.py']
        kernels,weights,assets,records,indices=load_assets(root)
        inputs={str(p.relative_to(root)):dict(sha256=digest(p),bytes=p.stat().st_size) for p in set(previous+references+assets+source)}
        task_path=Path('C:/Users/李咏晨/Downloads/N03-A-EXP1_%E5%8D%95%E7%82%B9%E5%85%89%E8%B0%B1NNLS%E6%8E%A2%E7%B4%A2%E6%80%A7%E9%AA%8C%E8%AF%81_Codex%E4%BB%BB%E5%8A%A1%E4%B9%A6.md')
        task=dict(path=str(task_path),sha256=digest(task_path))
        # 先验证上轮记录的原始输入仍一致，不将历史G0误改为PASS。
        old_manifest=json.loads((root/'reports/N03/00_manifest.json').read_text(encoding='utf-8'))
        prior_input_changes=[p for p,d in old_manifest['inputs'].items() if digest(root/p)!=d['sha256']]
        critical_changes=[p for p in prior_input_changes if p!='README.md']
        if critical_changes:raise RuntimeError(f'上轮原始输入发生变化：{critical_changes}')
        truth_library=library();noise_seeds=[20261021,20261022,20261023]
        config=dict(notice=NOTICE,scope='EXP1-A/B/C only',original_N03_G0='FAIL_UNCHANGED',
                    N02_G2_G3_Numerics='FAIL_UNCHANGED',wavelengths_nm=WAVELENGTHS.tolist(),
                    sensor_indices_zero_based=indices,weights_RGB=weights.tolist(),
                    weight_rule='真实波长精确匹配；原31点绿色响应和作所有通道共同分母；不乘Delta-lambda、不交换R/B',
                    spectrum_unit='每带已积分相对能量；所有真值sum(s)=1',
                    grid=dict(pitch_um=1,roi=[512,512],observations=3*512*512,axis_center='像元间(0,0)um',
                              delta_pixel=[256,256],delta_coordinate_um=[.5,.5],boundary='固定PSF ROI，无卷积/平移/额外裁切'),
                    normalization='shape_only; each archived ROI normalized_psf sums to 1',
                    throughput_aware='NOT_RUN：归档捕获率未完成数值认证；不能解释绝对硬件性能',
                    noise=dict(mode='common_absolute_noise',reference='B2_spiral_PSF，预定义均匀谱s=1/9',
                               levels_db=[40,30],seeds=noise_seeds,
                               sigma_formula='||A_B2*(1/9)||_2 / sqrt(786432) * 10^(-reference_SNR_dB/20)',
                               shared='各光学方案及所有谱共用相同sigma；同谱/种子共用同一全ROI高斯噪声场；两SNR级也复用标准场',
                               rng='default_rng(SeedSequence([seed,spectrum_index]))'),
                    solver='scipy.optimize.nnls; exact orthogonal SVD compression; no spectral prior',
                    numerical_rank_rule='sigma > eps_float64 * max(A.shape) * sigma_max',
                    solver_scaling='三组统一除以B2的sigma_max；不是列归一化',
                    spectra=truth_library,random_spectrum_seed=20261020,precision='float64',device='CPU',
                    optional_25bands_and_Tikhonov='NOT_RUN；完成必要A/B/C后停止',git_before=git_before,
                    environment=dict(python=sys.version,executable=sys.executable,numpy=np.__version__,scipy=scipy.__version__,
                                     matplotlib=matplotlib.__version__,torch=torch.__version__,platform=platform.platform(),
                                     cuda_available=torch.cuda.is_available(),
                                     thread_env={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']}),
                    input_manifest=inputs,task_source=task,old_manifest_read=True,
                    changes_since_previous_audit=prior_input_changes,
                    previous_README_policy='允许用户既有README变化；按本轮开始字节保护，不覆盖或回滚')
        dump(out/'run_config.json',config)
        event('PREREGISTERED',spectra=len(truth_library),bands=9,noise_seeds=noise_seeds)
        matrices={name:point_matrix(kernels[name],weights) for name in MODELS}
        factors={name:factorize(matrices[name]) for name in MODELS}
        spec=importlib.util.spec_from_file_location('exp1_validation',source[-1]);tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
        checks=tests.validate(root,kernels,weights,matrices,factors,indices)
        validation=dict(checks=checks,passed=sum(c['passed'] for c in checks),failed=sum(not c['passed'] for c in checks))
        dump(out/'validation_results.json',validation)
        if validation['failed']:raise RuntimeError('STOP-E：独立前向或基础数值测试失败')
        event('EXP1_ENTRY_PASS',tests=validation['passed'])
        diagnostics={};cosines={}
        for name in MODELS:
            a=matrices[name];u,b,sv,rank,tol=factors[name];norms=np.linalg.norm(a,axis=0)
            cosine=(a.T@a)/norms[:,None]/norms[None,:];cosines[name]=cosine
            off=cosine[~np.eye(9,dtype=bool)]
            diagnostics[name]=dict(shape=list(a.shape),rank=rank,rank_tolerance=float(tol),singular_values=sv.tolist(),
                                   sigma_min_over_max=float(sv[-1]/sv[0]),
                                   kappa=float(sv[0]/sv[-1]) if rank==9 else 'rank_deficient',
                                   nonzero_subspace_kappa=float(sv[0]/sv[rank-1]),
                                   column_norms=norms.tolist(),normalized_column_cosine=cosine.tolist(),
                                   max_offdiagonal_cosine=float(off.max()),mean_offdiagonal_cosine=float(off.mean()),
                                   svd_relative_reconstruction=float(np.linalg.norm(a-u@b)/np.linalg.norm(a)))
        dump(out/'matrix_diagnostics.json',diagnostics)
        reference=np.linalg.norm(matrices[MODELS[2]]@np.full(9,1/9));n=matrices[MODELS[2]].shape[0]
        scale=factors[MODELS[2]][2][0]
        dump(out/'noise_calibration.json',dict(reference_signal_l2=float(reference),observations=n,
                                              sigmas={str(db):float(reference/np.sqrt(n)*10**(-db/20)) for db in [40,30]},
                                              common_solver_scale=float(scale)))
        # 构造同总能量、非负、不同光谱却具有相同控制观测的显式反例。
        _,_,vt=np.linalg.svd(np.vstack([weights,np.ones(9)]),full_matrices=True)
        z=vt[-1];alpha=.5*np.min((np.ones(9)/9)[abs(z)>1e-12]/abs(z[abs(z)>1e-12]))
        s0=np.ones(9)/9;s1=s0+alpha*z
        evidence=dict(spectrum_0=s0.tolist(),spectrum_1=s1.tolist(),spectral_distance=float(np.linalg.norm(s1-s0)),
                      sums=[float(s0.sum()),float(s1.sum())],
                      observation_relative_difference={name:float(np.linalg.norm(matrices[name]@(s1-s0))/np.linalg.norm(matrices[name]@s0)) for name in MODELS})
        dump(out/'nonuniqueness_example.json',evidence)
        rows=[];solutions=[]
        def recover(case,condition,seed,sigma,z_norm2,z_projection):
            s=np.array(case['truth'])
            for name in MODELS:
                u,b,sv,rank,tol=factors[name];clean=b@s
                projected_noise=z_projection[name]*sigma
                yprojected=clean+projected_noise
                orth2=max(0.,z_norm2-float(z_projection[name]@z_projection[name]))*sigma*sigma
                estimate,status=solve_nnls(b,yprojected,scale)
                residual2=float(np.linalg.norm(b@estimate-yprojected)**2)+orth2
                ynorm=float(np.sqrt(yprojected@yprojected+orth2))
                quality=spectral_metrics(s,estimate,WAVELENGTHS)
                peakset=np.flatnonzero(np.isclose(s,s.max(),rtol=0,atol=1e-15))
                quality['peak_error_nm']=float(min(abs(WAVELENGTHS[np.argmax(estimate)]-WAVELENGTHS[peakset])))
                row=dict(model=name,spectrum=case['name'],kind=case['kind'],condition=condition,seed=seed,
                         **quality,relative_sensor_residual=float(np.sqrt(residual2)/max(ynorm,1e-300)),
                         signal_l2=float(np.linalg.norm(clean)),observation_l2=ynorm,noise_std=sigma,
                         noise_l2=float(np.sqrt(z_norm2)*sigma),
                         actual_realized_SNR_db=float(20*np.log10(np.linalg.norm(clean)/(np.sqrt(z_norm2)*sigma))) if sigma else None,
                         solver_status=status['status'],nonnegative=bool(estimate.min()>=0),
                         reduced_scaled_residual=status['reduced_scaled_residual'],
                         two_peak_support_match=bool(set(np.argsort(estimate)[-2:])==set(np.flatnonzero(s))) if case['kind']=='double' else None)
                rows.append(row);solutions.append(dict(**row,truth=s.tolist(),estimate=estimate.tolist()))
        zeros={name:np.zeros(factors[name][3]) for name in MODELS}
        for case in truth_library:recover(case,'noiseless',0,0.,0.,zeros)
        event('NOISELESS_COMPLETE',solves=len(rows))
        for i,case in enumerate(truth_library):
            for seed in noise_seeds:
                noise=np.random.default_rng(np.random.SeedSequence([seed,i])).normal(size=n)
                znorm2=float(noise@noise);proj={name:factors[name][0].T@noise for name in MODELS}
                for db in [40,30]:recover(case,f'common_absolute_{db}dB',seed,float(reference/np.sqrt(n)*10**(-db/20)),znorm2,proj)
            if i%6==5:event('NOISE_PROGRESS',spectra_complete=i+1,solves=len(rows))
        dump(out/'spectra_results.json',solutions)
        with (out/'metrics.csv').open('x',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        summary=[]
        for condition in ['noiseless','common_absolute_40dB','common_absolute_30dB']:
            for name in MODELS:
                selected=[r for r in rows if r['model']==name and r['condition']==condition]
                seeds=sorted(set(r['seed'] for r in selected));result=dict(condition=condition,model=name,cases=len(selected),replicates=len(seeds))
                for key in ['spectral_NRMSE','SAM_deg','relative_sensor_residual','relative_amplitude_bias','peak_error_nm']:
                    seedmeans=[np.mean([r[key] for r in selected if r['seed']==seed and r[key] is not None]) for seed in seeds]
                    result[key+'_mean']=float(np.mean(seedmeans));result[key+'_seed_std']=float(np.std(seedmeans,ddof=1)) if len(seeds)>1 else 0.
                result['actual_SNR_range_db']=[min(r['actual_realized_SNR_db'] for r in selected),max(r['actual_realized_SNR_db'] for r in selected)] if condition!='noiseless' else None
                summary.append(result)
        dump(out/'summary_metrics.json',summary)
        # 固定展示谱型，不根据测试结果挑选最佳曲线。
        for case_name in ['onehot_540','near_equal','broad_510','random_0']:
            fig,axes=plt.subplots(1,3,figsize=(13,4.8))
            for ax,condition in zip(axes,['noiseless','common_absolute_40dB','common_absolute_30dB']):
                items=[r for r in solutions if r['spectrum']==case_name and r['condition']==condition and r['seed'] in [0,noise_seeds[0]]]
                ax.plot(WAVELENGTHS,items[0]['truth'],'k-o',label='GT',linewidth=2)
                for item in items:ax.plot(WAVELENGTHS,item['estimate'],'--o',ms=3,label=item['model'])
                ax.set(title=condition,xlabel='Wavelength (nm)',ylabel='Band-integrated relative energy');ax.grid(alpha=.2);ax.legend(fontsize=7)
            figure_finish(fig,out/f'figures/spectrum_{case_name}.png',f'{case_name}; NNLS; no spectral prior; noisy panels seed={noise_seeds[0]}')
        fig,axes=plt.subplots(1,3,figsize=(12,4.8))
        for name in MODELS:
            d=diagnostics[name];sv=np.array(d['singular_values'])
            axes[0].semilogy(range(1,10),sv/sv[0],'-o',label=name)
            axes[1].semilogy(WAVELENGTHS,d['column_norms'],'-o',label=name)
            axes[2].plot(WAVELENGTHS,weights[MODELS.index(name)],'-o',label=['R','G','B'][MODELS.index(name)])
        axes[0].set(xlabel='Singular index',ylabel='sigma / sigma_max');axes[1].set(xlabel='Wavelength (nm)',ylabel='Raw column L2 norm');axes[2].set(xlabel='Wavelength (nm)',ylabel='Physical response weight')
        for ax in axes:ax.legend(fontsize=7);ax.grid(alpha=.2)
        figure_finish(fig,out/'figures/matrix_svd_norms_response.png','Measurement matrix diagnostics (no noise)')
        fig,axes=plt.subplots(1,3,figsize=(12,4.8))
        for ax,name in zip(axes,MODELS):
            im=ax.imshow(cosines[name],vmin=0,vmax=1,cmap='viridis');ax.set_title(name)
            ax.set_xticks(range(9),WAVELENGTHS.astype(int),rotation=90);ax.set_yticks(range(9),WAVELENGTHS.astype(int));fig.colorbar(im,ax=ax,shrink=.7)
        figure_finish(fig,out/'figures/column_cosine.png','Normalized column cosine (diagnostic only; solves use raw response)')
        fig,axes=plt.subplots(1,2,figsize=(10,4.8))
        order=['noiseless','common_absolute_40dB','common_absolute_30dB']
        for ax,key in zip(axes,['spectral_NRMSE','SAM_deg']):
            for name in MODELS:
                items=[next(r for r in summary if r['condition']==c and r['model']==name) for c in order]
                ax.errorbar(range(3),[r[key+'_mean'] for r in items],yerr=[r[key+'_seed_std'] for r in items],marker='o',capsize=3,label=name)
            ax.set_xticks(range(3),['No noise','Reference 40 dB','Reference 30 dB']);ax.set_ylabel(key);ax.grid(alpha=.2);ax.legend(fontsize=7)
        figure_finish(fig,out/'figures/noise_summary.png','NNLS, no spectral prior; common absolute AWGN; error bars = SD of 3 seed means over 18 spectra')
        fig,axes=plt.subplots(3,3,figsize=(9,9))
        for ax,h,wave in zip(axes.ravel(),kernels[MODELS[2]],WAVELENGTHS):
            ax.imshow(h,origin='lower',extent=[-256,256,-256,256],cmap='inferno');ax.set_title(f'{wave:g} nm');ax.set_xlabel('um');ax.set_ylabel('um')
        figure_finish(fig,out/'figures/archived_psfs.png','Archived normalized B2 PSFs; fixed full ROI, no alignment')
        # 额外展示预定义全谱集合中的最差案例，保留负结果。
        worst=max((r for r in solutions if r['model']==MODELS[2] and r['condition']=='common_absolute_30dB'),key=lambda r:r['spectral_NRMSE'])
        fig,ax=plt.subplots(figsize=(8,4.8));ax.plot(WAVELENGTHS,worst['truth'],'k-o',label='GT')
        for name in MODELS:
            item=next(r for r in solutions if r['model']==name and r['spectrum']==worst['spectrum'] and r['condition']==worst['condition'] and r['seed']==worst['seed'])
            ax.plot(WAVELENGTHS,item['estimate'],'--o',label=name)
        ax.set(xlabel='Wavelength (nm)',ylabel='Band-integrated relative energy');ax.legend(fontsize=8)
        figure_finish(fig,out/'figures/worst_spiral_case.png',f'Post-hoc worst B2 NRMSE: {worst["spectrum"]}, reference 30 dB, seed={worst["seed"]}')
        changed=[p for p,d in inputs.items() if digest(root/p)!=d['sha256']]
        if changed:raise RuntimeError(f'原输入被修改：{changed}')
        event('EXPERIMENT_COMPLETE',solves=len(rows),solver_failures=sum(r['solver_status']!='SUCCESS' for r in rows),input_changes=changed)
        lines=['# EXP1 探索性结果', '',NOTICE,'',
               'EXP1-A/B/C已完成，EXP1-ENTRY PASS；原N03-G0 FAIL、N02 G2/G3_Numerics FAIL保持不变。未做25波段、正则化、物理像元重采样或失配实验。','',
               '## 契约与实现','',
               '9波长固定为420/450/480/510/540/570/600/630/660nm；对应31点相机响应索引2/5/8/11/14/17/20/23/26（从0开始），R/G/B不交换。共同除以原31点绿色曲线之和，不乘Delta-lambda。s是每带已积分能量，所有真值总和1。',
               '采用shape_only、1um native-grid diagnostic、512×512固定ROI。B0统一delta位于(+0.5,+0.5)um；B1复制540nm；B2保留归档峰位。半像元轴心不变，无图像卷积，无reflect边界、gamma、裁剪、逐通道曝光或重新居中。',
               'throughput_aware仅讨论可行性：可按raw_roi乘1um²保留捕获率，但因该通量尚未完成数值认证本轮不运行；shape_only舍弃73.61%–88.58%类ROI捕获差异，不能解释真实相机/硬件优势。',
               'A为786432×9 float64，行顺序R全部像元、G全部像元、B全部像元，像元按行优先。独立渲染逐波长逐通道相加强度；建矩阵采用广播与轴变换。',
               '求解使用SVD正交压缩：A=UB，||As-y||²=||Bs-Uᵀy||²+||(I-UUᵀ)y||²，第二项不依赖s。仅舍弃数值零奇异方向，保留全部非零子空间；不是列归一化。NNLS全部三组共用相同标量缩放，且无谱平滑/稀疏先验。原矩阵、压缩目标与KKT有实际测试。',
               '噪声只采用common_absolute_noise。预先定义B2均匀谱为参考，而非分别给三模型或各测试谱调曝光；所有模型/谱共享sigma，同谱/种子共享完整高斯噪声场。40/30dB是参考名义SNR，实际SNR逐例见metrics.csv。此选择会让delta的实际SNR远高于扩散PSF，正是固定每像元读噪声预算下的控制结果，不等同真实Poisson相机。',
               '## 数值诊断','', '|模型|秩|sigma_min/max|条件数|最大非对角余弦|', '|---|---:|---:|---:|---:|']
        for name,d in diagnostics.items():lines.append(f'|{name}|{d["rank"]}|{d["sigma_min_over_max"]:.6g}|{d["kappa"]}|{d["max_offdiagonal_cosine"]:.6g}|')
        lines+=['','秩阈值eps×max(A.shape)×sigma_max；rank_deficient明确表示非唯一，非零子空间条件数另存JSON。列范数保留原响应，归一列余弦仅用于诊断。','',
                '## 三组恢复数据','', '|条件|模型|NRMSE均值±种子SD|SAM度均值±种子SD|传感器相对残差|', '|---|---|---:|---:|---:|']
        for r in summary:lines.append(f'|{r["condition"]}|{r["model"]}|{r["spectral_NRMSE_mean"]:.6g} ± {r["spectral_NRMSE_seed_std"]:.3g}|{r["SAM_deg_mean"]:.6g} ± {r["SAM_deg_seed_std"]:.3g}|{r["relative_sensor_residual_mean"]:.6g}|')
        lines+=['','NRMSE=||ŝ-s||₂/||s||₂；SAM=acos(sᵀŝ/(||s||₂||ŝ||₂))的角度值，预测全零则null而非伪造0度。幅值偏差同时保存sum(ŝ)-sum(s)、相对总能量偏差和L2幅值偏差。主峰误差对真值并列最高峰取最近者；双峰另存两最高恢复带是否匹配真实支撑，不能只靠主峰判断双峰分辨。',
                '每条件先对全部18谱取均值，再对3个种子求均值/样本SD（不是把54个样本混为3次重复）；无噪声只有1次。所有378次逐例结果和真值/解完整保存。','',
                '## 六项复盘','']
        b2diag=diagnostics[MODELS[2]]
        lines.append(f'1. B2数值秩{b2diag["rank"]}，控制组秩3；B2条件数{b2diag["kappa"]}，9带子集未表现出严重病态。无噪声及两个共享绝对噪声条件下，B2的平均光谱误差均低于B0/B1，支持本归档数值模型、精确已知位置下的9带探索性编码增益；不能把满秩当作任意噪声下可稳定恢复。')
        for kind in ['onehot','double','broad','random']:
            subset=[r for r in rows if r['model']==MODELS[2] and r['kind']==kind and r['condition']=='common_absolute_30dB']
            lines.append(f'   - {kind}：参考30dB时B2平均NRMSE={np.mean([r["spectral_NRMSE"] for r in subset]):.6g}，平均SAM={np.mean([r["SAM_deg"] for r in subset]):.6g}度。')
        lines += [f'2. 预定义全谱中B2最差噪声个例是{worst["spectrum"]}，seed={worst["seed"]}，NRMSE={worst["spectral_NRMSE"]:.6g}，已单独画图；近双峰/远双峰和单带全覆盖，成功失败项均保留。',
                  '3. 本轮仅报告统一绝对噪声口径，未做每模型自身归一的mathematical_SNR。实际信号范数、sigma、实现噪声范数和实际SNR逐例公开；不能把参考SNR标签当作各模型的实际SNR。本轮B2从40到30dB未快速失效，但这只覆盖两个较轻噪声点。低误差也来自786432个独立白噪声观测拟合仅9个未知量：噪声总范数大部分在A列空间之外，谱估计仅受投影噪声影响。不得据此预言相关噪声、背景或模型失配下同样精确。',
                  '4. 对照仅支持整体波长依赖PSF的编码差异；没有旋转消融，不能把差异唯一归因于螺旋旋转。',
                  '5. 原生1um网格、shape_only、精确已知位置与精确同模型合成/反演均为理想化假设；实际像元积分、通量、材料标定、PSF失配和原数值收敛问题足以改变结论。NNLS成功仅指优化成功，不表示秩亏解等于真值。',
                  '6. 建议可单独审核25原生波段与模型失配/面积积分的EXP2探索，并继续独立的物理数值认证。物理认证与本次算法探索分开标注；本轮不执行EXP2或新的求积。','',
                  '## 非唯一性证据','',
                  f'nonuniqueness_example.json保存两条总能量相同、非负且不同的光谱；谱距离{evidence["spectral_distance"]:.6g}，对应各组相对观测差为{evidence["observation_relative_difference"]}。控制组即使残差极小仍可恢复错误光谱。','',
                  '## 测试、产物与运行','',
                  f'{validation["passed"]}项PASS、{validation["failed"]}项FAIL；数值证据见validation_results.json。测试涵盖全部三模型×9列的独立渲染、多谱前向、伴随、线性、零输入、物理RGB toy、解析NNLS、秩亏、控制核相同和压缩残差/KKT。',
                  '新增代码仅在integration/single_spiral_to_hsi/n03_exp1及tests/test_n03_exp1.py；新增结果仅在本EXP1目录。输入SHA、Git HEAD/dirty、依赖、光谱生成规则与种子均在run_config.json。旧输入及用户已修改README的前后SHA保持不变；未Git提交、回滚、删除或修改框架。',
                  '图表：figures/archived_psfs.png、matrix_svd_norms_response.png、column_cosine.png、noise_summary.png、spectrum_onehot_540.png、spectrum_near_equal.png、spectrum_broad_510.png、spectrum_random_0.png、worst_spiral_case.png。全部图带探索声明。',
                  '逐例数据metrics.csv/spectra_results.json；汇总summary_metrics.json；矩阵诊断matrix_diagnostics.json；真实事件日志logs/events.jsonl；噪声标定noise_calibration.json。','',
                  '## P0/P1/P2与停止位置','',
                  '- P0：没有工程ENTRY失败；原G0及N02数值认证失败事实仍保留，物理性能未认证。',
                  '- P1：精确模型下的9带优势不能推广为真实相机、完整HSI、双孔径或旋转单机制结论；后续需失配/采样和物理可信性证据。',
                  '- P2：18条合成谱、每噪声3种子是首轮规模，尚无25带、谱平滑、Poisson、实测光谱或未知位置实验。',
                  '完成EXP1后停止，请交ChatGPT审核。']
        (out/'result_summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        command=f"& '{sys.executable}' -B E:\\SH\\integration\\single_spiral_to_hsi\\n03_exp1\\run_exp1.py --output E:\\SH\\reports\\N03\\EXP1_replay_unique"
        (out/'README.md').write_text('# EXP1\n\n'+NOTICE+'\n\nEXP1-A/B/C完成；只验证归档数值PSF的点源谱反演，原G0 FAIL保持不变。数值结论见result_summary.md。\n\n工作目录E:\\SH，使用已有环境；先将OMP_NUM_THREADS、MKL_NUM_THREADS、OPENBLAS_NUM_THREADS设为4。新输出目录必须尚不存在。\n\n```powershell\n'+command+'\n```\n\n入口先运行全部基础检查，不通过即STOP-E；通过才运行实验。精确实际调用与环境见logs/run_record.json。\n',encoding='utf-8')
        record=dict(status='COMPLETE_EXP1_ONLY',entry='PASS',original_G0='FAIL_UNCHANGED',seconds=time.perf_counter()-start,
                    command=subprocess.list2cmdline([sys.executable,'-B',*sys.argv]),tests=validation,solves=len(rows),
                    inputs_unchanged=not changed,git_after=git('status','--short','--untracked-files=all'))
        dump(out/'logs/run_record.json',record)
        event('DELIVERED',seconds_total=time.perf_counter()-start)
        dump(out/'artifact_manifest.json',{str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file()})
    except Exception:
        (out/'logs/failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':main()
