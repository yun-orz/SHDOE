"""EXP2逐条件统计与中文报告、实际实验图表。"""
import csv
import json
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from forward import WAVES,MODELS

NOTICE='EXP2 exploratory; N02 G2/G3_Numerics=FAIL; N03 G0=FAIL. No certified physical DOE performance.'


def save_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def summarize(rows):
    groups=defaultdict(list)
    keys=['phase','model','protocol','shape_mode','reconstruction','perturbation_type','perturbation_level','perturbation_id','P_in','read_sigma_e','target_SNR_db','grid_pitch_um']
    for row in rows:groups[tuple(row.get(k) for k in keys)].append(row)
    result=[]
    for group,items in groups.items():
        row=dict(zip(keys,group));row.update(n=len(items),n_spectra=len(set(x['spectrum'] for x in items)),n_seeds=len(set(x['seed'] for x in items)))
        for key in ['NRMSE','SAM_deg','amplitude_bias','relative_sensor_residual','peak_error_nm','actual_SNR_db','expected_electrons','signal_l2','noise_l2']:
            values=[x[key] for x in items if x.get(key) is not None]
            if not values:continue
            seedmeans=[]
            for seed in sorted(set(x['seed'] for x in items)):
                v=[x[key] for x in items if x['seed']==seed and x.get(key) is not None]
                if v:seedmeans.append(float(np.mean(v)))
            row.update({key+'_mean':float(np.mean(values)),key+'_median':float(np.median(values)),
                        key+'_max':float(max(values)),key+'_seed_std':float(np.std(seedmeans,ddof=1)) if len(seedmeans)>1 else 0,
                        key+'_seed_means':json.dumps(seedmeans)})
        worst=max(items,key=lambda x:x['NRMSE']);row['worst_spectrum']=worst['spectrum'];row['worst_seed']=worst['seed']
        result.append(row)
    return result


def finish(fig,path,title):
    fig.suptitle(title+'\n9 bands 420–660 nm / 30 nm; NNLS, no spectral prior',fontsize=10)
    fig.text(.5,.012,NOTICE,ha='center',fontsize=7)
    fig.tight_layout(rect=(0,.055,1,.91));fig.savefig(path,dpi=150);plt.close(fig)


def publish(out,rows,summary,diags,diag25,energy,tests,config,preflight,nominal_kernels,native_kernel,mismatch_info):
    full=[r for r in rows if r['phase']=='full']
    sumfull=[r for r in summary if r['phase']=='full']
    # S0/S1及各对照的奇异值，秩亏数值尾部保留，不把其解释为实际信息。
    fig,axes=plt.subplots(1,2,figsize=(11,4.8))
    for name,d in diags.items():
        if name.startswith('shape_only') or name=='S0_native_B2':
            sv=np.array(d['singular_values']);axes[0].semilogy(range(1,10),sv/sv[0],'-o',label=name)
            axes[1].plot(WAVES,d['column_norms'],'-o',label=name)
    axes[0].set(xlabel='Singular index',ylabel='sigma/sigma_max');axes[1].set(xlabel='Wavelength (nm)',ylabel='Raw weighted column norm')
    for ax in axes:ax.legend(fontsize=7);ax.grid(alpha=.2)
    finish(fig,out/'figures/singular_values_9band.png','Native vs conservative detector-area sampling; shape_only')
    fig,axes=plt.subplots(1,2,figsize=(9,4.8))
    p=config['detector']['pitch_um'];edge=config['detector']['edges_um']
    axes[0].imshow(native_kernel,origin='lower',extent=[-256,256,-256,256],cmap='inferno');axes[0].set_title('540nm archived 1um grid')
    axes[1].imshow(nominal_kernels,origin='lower',extent=[edge[0],edge[-1],edge[0],edge[-1]],cmap='inferno');axes[1].set_title(f'Area-integrated {p:.9f}um grid')
    for ax in axes:ax.set(xlabel='x (um)',ylabel='y (um)',xlim=(-70,70),ylim=(-70,70))
    finish(fig,out/'figures/sampling_psf_comparison.png','B2 540nm shape_only; no recentering; 70um display window only')
    fig,axes=plt.subplots(1,4,figsize=(15,4.8))
    for ax,family in zip(axes,['common_shift_x','chromatic_shift','gaussian_blur','rgb_gain']):
        for protocol,marker in [('mismatch_noiseless','o'),('mismatch_Q40','s')]:
            for recon,style in [('M1_nominal','-'),('M2_oracle','--')]:
                items=[r for r in sumfull if r['protocol']==protocol and r['perturbation_type']==family and r['reconstruction']==recon]
                items.sort(key=lambda r:r['perturbation_level'])
                ax.semilogy([r['perturbation_level'] for r in items],[max(r['NRMSE_mean'],1e-16) for r in items],style+marker,label=protocol+'/'+recon,ms=3)
        ax.set(title=family,xlabel='detector pixel or relative gain',ylabel='Mean spectral NRMSE');ax.grid(alpha=.2);ax.legend(fontsize=5.5)
    finish(fig,out/'figures/mismatch_nrmse_log.png','B2 shape_only: true-only mismatch; M2 is oracle, not realistic performance')
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for i,mode in enumerate(['shape_only','throughput_aware']):
        for name in MODELS:
            pp=sorted([r for r in sumfull if r['protocol']=='P' and r['shape_mode']==mode and r['model']==name],key=lambda r:(r['P_in'],r['read_sigma_e']))
            axes[i,0].errorbar(range(len(pp)),[r['NRMSE_mean'] for r in pp],yerr=[r['NRMSE_seed_std'] for r in pp],marker='o',label=name,capsize=3)
            qq=sorted([r for r in sumfull if r['protocol']=='Q' and r['shape_mode']==mode and r['model']==name],key=lambda r:r['target_SNR_db'])
            axes[i,1].errorbar([r['target_SNR_db'] for r in qq],[r['NRMSE_mean'] for r in qq],yerr=[r['NRMSE_seed_std'] for r in qq],marker='o',label=name,capsize=3)
        axes[i,0].set_xticks(range(4),['1e4 / 1e','1e4 / 3e','1e5 / 1e','1e5 / 3e']);axes[i,0].set_xlabel('P_in / read RMS');axes[i,0].set_title('P: equal incident budget; '+mode)
        axes[i,1].set_xlabel('Matched realized array SNR (dB)');axes[i,1].set_title('Q: model-specific noise amplitude; '+mode)
        for ax in axes[i]:ax.set_yscale('log');ax.set_ylabel('NRMSE');ax.legend(fontsize=7);ax.grid(alpha=.2)
    finish(fig,out/'figures/noise_budget_comparison.png','P and Q are separate protocols; throughput q(lambda) shared by all optical controls')
    # 按B2最困难的P条件对全部谱/种子排序选最好、中位、最坏，明确是事后选例。
    selection=sorted([r for r in full if r['model']==MODELS[2] and r['protocol']=='P' and r['shape_mode']=='shape_only' and r['P_in']==1e4 and r['read_sigma_e']==3],key=lambda r:r['NRMSE'])
    chosen=[selection[0],selection[len(selection)//2],selection[-1]]
    fig,axes=plt.subplots(1,3,figsize=(12,4.8))
    for ax,row,label in zip(axes,chosen,['Best','Median-ranked','Worst']):
        ax.plot(WAVES,row['truth'],'k-o',label='GT')
        for name in MODELS:
            item=next(r for r in full if r['model']==name and r['protocol']=='P' and r['shape_mode']=='shape_only' and r['P_in']==1e4 and r['read_sigma_e']==3 and r['spectrum']==row['spectrum'] and r['seed']==row['seed'])
            ax.plot(WAVES,item['estimate'],'--o',ms=3,label=name)
        ax.set(title=f'{label}: {row["spectrum"]}\nseed={row["seed"]}; B2 NRMSE={row["NRMSE"]:.3g}',xlabel='Wavelength (nm)',ylabel='Integrated band energy');ax.legend(fontsize=6);ax.grid(alpha=.2)
    finish(fig,out/'figures/spectrum_best_median_worst.png','Post-hoc ranked examples: shape_only P_in=1e4, read RMS=3e')
    if diag25:
        fig,ax=plt.subplots(figsize=(7,4.8))
        for label,d in [('9 bands',diags['shape_only/'+MODELS[2]]),('25 bands (NO RECONSTRUCTION)',diag25)]:
            sv=np.array(d['singular_values']);ax.semilogy(range(1,len(sv)+1),sv/sv[0],'-o',ms=3,label=label)
        ax.set(xlabel='Singular index',ylabel='sigma/sigma_max');ax.legend(fontsize=8);ax.grid(alpha=.2)
        finish(fig,out/'figures/diagnostic_25bands.png','RGB-weighted detector matrix: 9 vs 25 native bands; diagnostic only')
    report=['# EXP2 结果报告','',NOTICE,'',
            '**范围与判定：EXP2已完成；G-impl、G-pilot、G-full通过。N03 G0与N02 G2/G3_Numerics继续FAIL。后续研究建议CONDITIONAL GO，不代表物理DOE验收通过。**','',
            '本轮只检验归档B2数值PSF在面积采样、精确模型及受控失配下的已知单点光谱反演。采样后的数值秩/条件数、失配代价和两种噪声协议的结果见下表；三模型的高低由数据决定，不预设B2必须胜出。','',
            '## 1. 来源、契约与实现','',
            preflight,
            '主矩阵行为RGB、行、列C顺序，列为9个按波长递增的谱带。谱系数为每带已积分入射量且真谱sum=1，不乘10/30nm。恢复不加光谱平滑或稀疏先验。',
            '矩阵用实际float64 SVD，NNLS沿用EXP1正交压缩的等价目标；压缩后补全零观测行至L+1行，目标严格不变，无新增先验。每次记录KKT/非负和全ROI残差。非零失配只施加A_true；M1始终用原标称A，M2用A_true仅作oracle，不计现实性能。',
            '主shape_only在detector面积积分后逐波长归一，裁切前能量另表保留。throughput_aware采用同一B2 q(lambda)=归档crop_fraction×detector_capture_from_normalized_ROI，外加到三组shape_only，且只乘一次；它是有限ASM域参考下的相对收集份额，不是绝对透过率/QE。',
            '协议P的全局电子比例K=1/max_l sum_c w(c,l)，在原31点响应上确定，三模型及两通量模式共用，确保模拟平均电子总数不超过P_in；这是预注册的模拟设定，不是实测QE。每像元独立Poisson，读噪声1/3e RMS为情景假设，理想三通道完整阵列，不含Bayer、暗电流、饱和、ADC、gamma或截断。读噪后允许负观测，Poisson rate始终非负。',
            '协议Q对每模型每谱单独缩放同一标准高斯方向，使全ROI实际20log10(||signal||/||noise||)匹配30/40dB；不减背景（模拟无背景）。P/Q的物理预算不同，不能只挑有利协议宣称硬件优越。',
            '失配幅度和实际每带位移/增益见model_mismatch.csv及perturbation_manifest.json；平移直接对平移后的源像元边界积分到detector，非周期、ROI外未知场按零。Gaussian核宽换算为um，通过连续高斯、源像元及接收像元的解析双重面积积分，避免小sigma离散采样核退化为delta；无任意5sigma截断，仅清除约1e-14的远尾浮点抵消量。形状模式重新归一，裁切损失单独保留。独立光学离散误差资产对照NOT_RUN：避免不确定不同采样/传播条件的合法等价性；未用PSF波长插值冒充传播。','',
            '## 2. 工程门与运行','',
            f'G-impl测试{len(tests)}项，PASS={sum(t["passed"] for t in tests)}，FAIL={sum(not t["passed"] for t in tests)}；tests.json保留每项数值。pilot先使用两单峰、两双峰、一宽谱、一随机谱及3种子，输出独立pilot_metrics.csv；通过后才full。',
            '首次EXP2_20261020_01在pilot发现SciPy 1.15.3对3×9欠定压缩NNLS返回零残差但KKT违反9.18e-7；立即停止，未进入full。已在固定B0/单600nm/seed20261022重现，增加零观测行（等价目标）后KKT恢复至约4e-17。回归测试覆盖该问题，旧失败目录完整保留。辅助定位时一次读取中文JSON遗漏UTF-8导致UnicodeDecodeError，显式指定编码后完成诊断，不涉及实验数据改写。',
            'EXP2_20261020_02已完整运行，但事后物理采样复核指出0.1detector pixel的Gaussian宽度小于fine像元，离散点采样卷积核低估模糊。本最终run改用连续高斯双面积积分并用独立quad数值积分核对；平移同样改为源像元直接到detector的精确重叠。原run完整保留，本报告结论只引用当前目录。',
            '输入与新源码SHA-256见input_manifest.json，环境/Git/种子和完整预注册见run_config.json，日志与耗时见logs/run_record.json、events.jsonl。所有旧文件前后保护见preservation.json。实际命令见run_commands.md。','',
            '## 3. 9带采样前后矩阵','',
            '|条件|shape|秩|条件数|smin/smax|最大列余弦|','|---|---|---:|---:|---:|---:|']
    for name,d in diags.items():report.append(f'|{name}|{d["shape"]}|{d["rank"]}|{d["kappa"]}|{d["sigma_min_over_max"]:.6g}|{d["max_column_cosine"]:.6g}|')
    report+=['','数值秩阈值eps_float64×max(A.shape)×sigma_max；rank_deficient不以非零子空间有限条件数掩盖。熵有效秩、Gram、逐波长列范数、完整SVD及相邻列余弦另存JSON。这是RGB加权矩阵而非裸PSF强度字典。',
             'sampling_energy_check.csv逐模型逐波长报告detector前后能量、outside和q；throughput_analysis.csv另列实际q及全部三组共享规则。面积积分严格在原fine ROI内，没有外插。','',
             '## 4. 失配：M0/M1/M2','',
             '|条件|重建|平均NRMSE|中位NRMSE|最坏NRMSE|平均SAM度|种子均值SD|','|---|---|---:|---:|---:|---:|---:|']
    for r in sumfull:
        if r['protocol'].startswith('mismatch') and r['reconstruction']=='M1_nominal':
            report.append(f'|{r["perturbation_id"]}/{r["protocol"]}|M1|{r["NRMSE_mean"]:.6g}|{r["NRMSE_median"]:.6g}|{r["NRMSE_max"]:.6g}|{r["SAM_deg_mean"]:.6g}|{r["NRMSE_seed_std"]:.3g}|')
    oracle=[r for r in full if r['reconstruction']=='M2_oracle' and r['protocol']=='mismatch_noiseless']
    report += ['',f'M2无噪声oracle全部案例平均NRMSE={np.mean([r["NRMSE"] for r in oracle]):.6g}，最坏={max(r["NRMSE"] for r in oracle):.6g}；它只验证模型失配确实是误差来源之一。M2全部逐条件统计同样在summary_metrics.csv，不替代M1。',
               'M0理想无噪声误差接近机器精度，以其作分母的失配倍数没有可靠解释。因此mismatch_ratios.csv主要比较相同种子、相同Q40口径的M1与无失配M0，同时保存绝对误差差值；分母小于1e-12时比值标null。',
               'B0/B1参加采样及P/Q主对照；本轮失配族只在B2上做M1/M2，没有追加可选基线失配全扫描。共同点位失配不等同未知位置恢复。','',
               '## 5. 协议P：相同入射预算','',
               '|模式|模型|P_in|read e|平均NRMSE|最坏|SAM度|实际SNR均值|期望总电子|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in sumfull:
        if r['protocol']=='P':report.append(f'|{r["shape_mode"]}|{r["model"]}|{r["P_in"]:.0f}|{r["read_sigma_e"]}|{r["NRMSE_mean"]:.6g}|{r["NRMSE_max"]:.6g}|{r["SAM_deg_mean"]:.6g}|{r["actual_SNR_db_mean"]:.4g}|{r["expected_electrons_mean"]:.6g}|')
    report+=['','同一P_in、同一谱、同通量模式下三组期望总电子相同（数值舍入容差），空间分布不同导致Poisson及读噪效应不同；没有分别调到相同探测电子总量。P协议阵列SNR允许不同，不能将其标签混作Q。','',
             '## 6. 协议Q：匹配实际阵列SNR','',
             '|模式|模型|目标SNR|平均NRMSE|中位|最坏|SAM度|种子均值SD|','|---|---|---:|---:|---:|---:|---:|---:|']
    for r in sumfull:
        if r['protocol']=='Q':report.append(f'|{r["shape_mode"]}|{r["model"]}|{r["target_SNR_db"]}|{r["NRMSE_mean"]:.6g}|{r["NRMSE_median"]:.6g}|{r["NRMSE_max"]:.6g}|{r["SAM_deg_mean"]:.6g}|{r["NRMSE_seed_std"]:.3g}|')
    report+=['','每例signal/noise范数、噪声尺度、actual_SNR、期望和实现电子数见metrics.csv、noise_calibration.csv；每条件n=18谱×3种子=54（确定性无噪声18例）。统计保存均值、中位、最坏、3个seed均值及其样本SD；不声称统计显著性。',
             'NRMSE=||estimate-truth||₂/||truth||₂，SAM为向量夹角度；恢复全零时SAM记null并单列零解数，不把零向量记0度。amplitude_bias=sum(estimate)-sum(truth)，同时保留相对能量偏差；主峰对并列真峰取最近波长。全ROI相对残差与谱误差分开记录，不能互相替代。','',
             '## 7. 25波段只读预诊断','']
    if diag25:
        report.append(f'25原生波长420–660nm/10nm，仅同detector网格shape_only的RGB加权矩阵：rank={diag25["rank"]}/25，kappa={diag25["kappa"]}，smin/smax={diag25["sigma_min_over_max"]:.6g}，最大列余弦={diag25["max_column_cosine"]:.6g}，最大相邻余弦={diag25["max_adjacent_column_cosine"]:.6g}，熵有效秩={diag25["effective_entropy_rank"]:.6g}。NO_RECONSTRUCTION。')
    else:report.append('NOT_RUN。')
    report+=['物理数值认证仍FAIL，25带密集谱相关可能放大噪声/失配；本轮没有任何25带谱真值、NNLS结果或恢复许可。','',
             '## 8. 数据驱动结论与替代解释','']
    s1=diags['shape_only/'+MODELS[2]]
    report.append(f'面积积分后9带B2数值秩{s1["rank"]}/9、条件数{s1["kappa"]}；S0相较EXP1的差异在preflight已核验。这个结论仅说明当前归档空间强度模式在所选采样下仍有线性可辨识性。')
    worst=max((r for r in full if r['reconstruction']=='M1_nominal'),key=lambda r:r['NRMSE'])
    report.append(f'失配M1最坏例：{worst["perturbation_id"]}、{worst["spectrum"]}、{worst["protocol"]}、seed={worst["seed"]}，NRMSE={worst["NRMSE"]:.6g}，SAM={worst["SAM_deg"]:.6g}度。全部负结果保留，不能用M2替代。')
    for protocol in ['P','Q']:
        for mode in ['shape_only','throughput_aware']:
            means={name:float(np.mean([r['NRMSE'] for r in full if r['protocol']==protocol and r['shape_mode']==mode and r['model']==name])) for name in MODELS}
            report.append(f'{protocol}/{mode}（仅描述预注册条件等权汇总，具体条件见上表）：平均NRMSE {means}。')
    report+=['',
             '- inverse crime仍存在于M0和oracle；M1才检查指定失配，不能覆盖所有真实标定误差。',
             '- 源传播的周期/输入积分伪影尚未认证；面积积分是探测层数学重采样，不修复传播层错误。',
             '- 粗像元面积、光轴落在四像元边界、零边界平移及shape归一都会影响灵敏度；真实Bayer、MTF和像元响应未验证。',
             '- 假设电子比例、读噪声和独立白噪声不同于实测相机；P/Q不可互换，shape_only也不能替代真实光通量。',
             '- 未做旋转消融，优势只能归于整体波长相关PSF；未实现未知位置、多点或完整场景恢复。','',
             '**下一步：CONDITIONAL GO。** 可审核后针对本轮最敏感的点位/响应误差做标定或鲁棒性改进，并继续独立N02物理数值认证。25带恢复、真实硬件优越性及场景重建均不由本实验自动放行。','',
             '本轮仅新增n03_exp2、test_n03_exp2.py和本唯一EXP2输出目录。未删除、改写旧代码/资产/README/历史报告，未Git提交。run_commands.md提供唯一新目录复跑命令；结束于本EXP2，等待ChatGPT审核。']
    (out/'result_summary.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
