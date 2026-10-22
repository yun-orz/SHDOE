"""按任务书六项格式报告真实证据，并独立核查归档。"""
import sys
sys.dont_write_bytecode=True
import csv
import json
import math
import time
import os
import stat
import ctypes
from pathlib import Path
import numpy as np
from optics import ROOT,sha,array_sha,config,design,measure
from audit import write,textfile,snapshot,now,git
from evaluate import load,csvwrite


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def diagnostics(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[]
    paths=[('standard_1um_pad2',out/'B2/cases/425nm.npz'),
           ('same_height_pad4',out/'convergence/cases/pad4_425nm.npz'),
           ('same_design_dx05',out/'convergence/cases/dx05_425nm.npz')]
    fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained')
    for col,(label,p) in enumerate(paths):
        raw,c,r=load(p);rr,cc=np.unravel_index(raw.argmax(),raw.shape)
        yy,xx=np.mgrid[-1:2,-1:2]
        mat=np.column_stack([np.ones(9),xx.ravel(),yy.ravel(),xx.ravel()**2,(xx*yy).ravel(),yy.ravel()**2])
        target=np.log(np.maximum(raw[rr-1:rr+2,cc-1:cc+2],np.finfo(float).tiny)).ravel()
        coef=np.linalg.lstsq(mat,target,rcond=None)[0]
        H=np.array([[2*coef[3],coef[4]],[coef[4],2*coef[5]]]); eig=np.linalg.eigvalsh(H)
        delta=-np.linalg.solve(H,coef[1:3])
        reason='HESSIAN_NOT_NEGATIVE' if max(eig)>=0 else 'OFFSET_EXCEEDS_ONE_PIXEL' if abs(delta).max()>1 else 'FIT_STABLE'
        rows.append(dict(condition=label,wavelength_nm=425,n01_status=r['n01_status'],reason=r['invalid_reason'],
            diagnostic_fit_reason=reason,hessian_eigenvalues=eig.tolist(),offset_pixels=delta.tolist(),
            log_fit_rmse=float(np.sqrt(np.mean((target-mat@coef)**2))),
            raw_argmax_x_um=float(c[cc]),raw_argmax_y_um=float(c[rr]),outside_ratio=r['outside_main_disk_ratio']))
        axes[0,col].imshow(raw,origin='lower',extent=[-256,256,-256,256],cmap='inferno')
        axes[0,col].set(xlim=(-60,60),ylim=(-60,60),xlabel='x (um)',ylabel='y (um)',title=f'425nm / {label}\n{r["n01_status"]} / {reason}')
        axes[0,col].plot(c[cc],c[rr],'c+')
        half=8
        axes[1,col].imshow(raw[rr-half:rr+half+1,cc-half:cc+half+1],origin='lower',cmap='inferno',
             extent=[c[cc-half]-.5*r['pitch_um'],c[cc+half]+.5*r['pitch_um'],c[rr-half]-.5*r['pitch_um'],c[rr+half]+.5*r['pitch_um']])
        axes[1,col].plot(c[cc],c[rr],'c+');axes[1,col].set(xlabel='x (um)',ylabel='y (um)',title=f'Unchanged raw local patch / dx={r["pitch_um"]:g}um')
    fig.suptitle('Frozen 3x3 log-quadratic localization audit; ASM128 / N02 B2 / scripts experiments/n02/reporting.py')
    fig.savefig(out/'425nm_fit_failure.png',dpi=150);plt.close(fig)
    csvwrite(out/'425nm_fit_diagnostics.csv',rows)
    # 蓝端不跨无效点连线，并保留原始候选的竞争峰和链接拒绝信息。
    with (out/'B2/adaptive_blue_metrics.csv').open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
    fig,ax=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for r in rr:
        w=float(r['wavelength_nm']);color='tab:blue' if r['n01_status']=='VALID' else 'red'
        ax[0].scatter(w,float(r['raw_angle_deg']),color=color)
        ax[1].scatter(float(r['main_peak_x_um']),float(r['main_peak_y_um']),color=color)
        if r['n01_status']!='VALID':ax[0].annotate(f'{w:g}nm invalid',(w,float(r['raw_angle_deg'])))
    ax[0].set(xlabel='Wavelength (nm)',ylabel='Raw angle (deg)',title='420-500nm + 421-429nm adaptive')
    ax[1].set(xlabel='x (um)',ylabel='y (um)',title='Peak positions; red = frozen invalid');ax[1].axis('equal')
    fig.suptitle('B2 / ASM128 dx1um pad2 / conditional identity; no cross-gap interpolation')
    fig.savefig(out/'blue_peak_diagnostics.png',dpi=150);plt.close(fig)
    return rows


def height_plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained')
    cc=config();d=design(cc);c=d['coord'];h=np.load(out/'B2/height_um.npy');cont=np.load(out/'B1/height_um.npy');mask=d['mask']
    for ax,a,name in [(axes[0,0],cont,'B1 continuous'),(axes[0,1],h,'B2 Q10 floor')]:
        im=ax.imshow(np.where(mask,a,np.nan),origin='lower',extent=[-1024,1024,-1024,1024],vmin=0,vmax=d['period_um'],cmap='viridis');ax.set(xlim=(-520,520),ylim=(-520,520),xlabel='x (um)',ylabel='y (um)',title=name);fig.colorbar(im,ax=ax,label='Height (um)')
    levels,cnt=np.unique(h[mask],return_counts=True);axes[0,2].bar(levels,cnt,width=.07);axes[0,2].set(xlabel='Height (um)',ylabel='Pupil pixel count',title='10 physical levels')
    axes[1,0].plot(c,cont[1024],label='continuous');axes[1,0].step(c,h[1024],where='mid',label='Q10');axes[1,0].set(xlim=(-500,500),xlabel='x (um), y=0.5um',ylabel='Height (um)');axes[1,0].legend()
    from scipy.ndimage import map_coordinates
    theta=np.linspace(-np.pi,np.pi,1000);r=400.;x=r*np.cos(theta);y=r*np.sin(theta)
    a=map_coordinates(h,[y+1023.5,x+1023.5],order=0)
    axes[1,1].plot(np.rad2deg(theta),a);axes[1,1].set(xlabel='Azimuth (deg), r=400um',ylabel='Height (um)',title='Angular height section')
    # 可见相位断点密度不代表真实侧壁坡度。
    grad=np.hypot(np.gradient(h,axis=0),np.gradient(h,axis=1));axes[1,2].imshow(grad,origin='lower',extent=[-1024,1024,-1024,1024],cmap='magma');axes[1,2].set(xlim=(-520,520),ylim=(-520,520),xlabel='x (um)',ylabel='y (um)',title='Sampled step diagnostic (um / pixel)')
    fig.suptitle('N02 B1/B2 / design 546.1nm / ASSUMED Cauchy / dx1um / scripts experiments/n02/reporting.py')
    fig.savefig(out/'height_design_maps_sections.png',dpi=150);plt.close(fig)


def artifact_verify(out):
    cfg=config();verified=[];maxe=0.;maxnorm=0.
    # 所有cases从保存原始强度复算；生成与评估的物理字段独立核对。
    for folder in out.iterdir():
        if not folder.is_dir() or not (folder/'cases').exists():continue
        cc=read(folder/'config.json') if (folder/'config.json').exists() else None
        if cc:
            h=np.load(folder/'height_um.npy',allow_pickle=False);hdigest=array_sha(h)
        for p in sorted((folder/'cases').glob('*.npz')):
            raw,c,r=load(p)
            assert np.isfinite(raw).all() and np.all(raw>=0) and raw.sum()>0
            with np.load(p,allow_pickle=False) as z:
                err=float(np.max(np.abs(z['normalized_psf']-raw/raw.sum())))
                maxnorm=max(maxnorm,err);assert err<1e-15
            assert np.isclose(raw.sum()*r['pitch_um']**2,r['crop_energy'],atol=1e-12,rtol=0)
            assert np.isclose(r['crop_fraction'],r['crop_energy']/r['raw_energy'],atol=1e-12,rtol=0)
            maxe=max(maxe,r['spectral_energy_accounting_error'])
            if cc:
                assert r['height_array_sha256']==hdigest
                rec=measure(raw,c,r,cc,r['wavelength_nm'])
                assert rec['n01_status']==r['n01_status'] and rec['n02_status']==r['n02_status']
                assert rec['halfmax_components']==r['halfmax_components']
                assert abs(rec['main_sidelobe_ratio']-r['main_sidelobe_ratio'])<1e-12
            verified.append(dict(path=str(p.relative_to(out)),sha256=sha(p),height_hash_match=bool(cc),
                raw_roi_energy=r['crop_energy'],energy_error=r['spectral_energy_accounting_error']))
    write(out/'artifact_verification.json',dict(status='PASS',verified_cases=len(verified),
        max_normalized_psf_error=maxnorm,max_parseval_error=maxe,cases=verified,
        scope='真实NPZ原始强度/归一副本/面积能量回读，已存高度SHA，冻结检测复算；不以工程核查覆盖科学FAIL'))
    return len(verified),maxe


def finalize(out,env,start):
    tests=read(out/'physics_tests.json');summaries=read(out/'baseline_summaries.json');b=summaries['B2']
    conv=read(out/'gate3_convergence.json');g3=read(out/'G3.json');fab=read(out/'gate3_fabrication.json')
    blue=read(out/'B2/dense_blue_summary.json');adaptive=read(out/'B2/adaptive_blue_summary.json')
    diag=diagnostics(out);height_plot(out)
    ncases,maxenergy=artifact_verify(out)
    # 全局G2显式包含蓝端门和符号代理，标准25点PASS不替代它。
    with (out/'B2/adaptive_blue_links.csv').open(encoding='utf-8-sig',newline='') as f:blue_links=list(csv.DictReader(f))
    G2='PASS' if b['G2']=='PASS' and blue['n02_valid']==blue['wave_count'] and all(r['credible']=='True' and r['n02_angle_gate']=='True' for r in blue_links) else 'FAIL'
    gates=dict(G0=dict(status='PASS',execution='SIMULATED',reason='12/12物理测试及冻结协议/历史路径审计'),
        G1=dict(status='PASS',execution='SIMULATED',reason='B2固定高度25标准通道物理/形态/链接与旋转成立'),
        G2=dict(status=G2,execution='SIMULATED',standard25=b['G2'],blue5nm='FAIL' if blue['n02_valid']<blue['wave_count'] else 'PASS',
            reason='425nm冻结3x3拟合不稳定；1nm局部若干角符号误差代理/缩放角差门不通过；不能仅报标准25点'),
        G3_Numerics=dict(status=g3['numerics'],execution='SIMULATED',reason='多个波长全域16um边缘能量未达冻结0.001门'),
        G3_Fabrication=dict(status=g3['fabrication_quantification'],execution='SIMULATED_ASSUMED',reason='完成有界假设扰动定量，实测工艺NOT_TESTED'))
    gates.update(read(out/'downstream_gates.json'))
    gates['GF']=dict(status='PASS',execution='SIMULATED',reason='完成本轮P0证据归档与独立回读；科研L1/L2/L3不因此通过')
    write(out/'gates.json',gates)
    before=read(out/'preservation_before.json');after=snapshot()
    changed=[p for p,v in before.items() if p not in after or after[p]!=v]
    extra=[p for p in after if p not in before]
    write(out/'preservation_after.json',after)
    write(out/'preservation_comparison.json',dict(status='PASS' if not changed else 'FAIL',
       original_file_count=len(before),changed_original_paths=changed,new_non_n02_paths=extra,
       scope='历史全部文件size/mtime；文本另比SHA；排除.git、__pycache__和隔离n02目录，不声称全部二进制内容SHA'))
    assert not changed,'历史保护核查失败'
    canonical={k:sha(out/'B2'/k) for k in ['height_um.npy','aperture_mask.npy','config.json']}
    canonical.update({str(p.relative_to(out/'B2')):sha(p) for p in (out/'B2/cases').glob('*.npz')})
    write(out/'B2/frozen_sha256.json',canonical)
    for name in canonical:os.chmod(out/'B2'/name,stat.S_IREAD)
    # Windows只读属性是误覆盖保护，不冒充密码学不可变存储。
    source_hash={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/n02').glob('*.py')}
    source_hash['configs/n02/baseline_B.yaml']=sha(ROOT/'configs/n02/baseline_B.yaml')
    write(out/'source_hashes_final.json',source_hash)
    records=[load(out/'B2/cases'/f'{w}nm.npz')[2] for w in range(420,661,10)]
    edge={int(r['wavelength_nm']):r['edge_fraction'] for r in records}
    convpad=[r for r in conv if r['condition']=='pad4'];convdx=[r for r in conv if r['condition']=='dx05'];ind=[r for r in conv if r['condition']=='independent_cpu_ASM']
    gpu=max((r.get('gpu_peak_bytes') or 0 for r in conv),default=0)
    ledger=[json.loads(x) for x in (out/'propagation_ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    total_seconds=sum(float(r.get('seconds',0)) for r in ledger if r['event']=='COMPLETE')
    table='| 项目 | 原W/C/F2（NON-FAIR REFERENCE） | N02硬环带B2 | 软环带 | 优化 | 证据 |\n|---|---|---|---|---|---|\n'
    table+=f'| 最大高度um | W 1.195884 / C 55.505381 / F2约10.668（原文件另核） | {b["max_height_um"]:.9f} | NOT_TESTED | NOT_TESTED | B2/height_metadata.json；历史N01-2A报告 |\n'
    table+='| 波段/材料/孔径 | 400–700nm / 熔融石英 / R1000um | 420–660nm / ASSUMED IP-Dip2 Cauchy / R500um | NOT_TESTED | NOT_TESTED | config_resolved.json |\n'
    table+=f'| 单峰通过数 | W14/31；C31/31；F2 12/13，蓝端失败 | 标准{b["n02_valid"]}/25；蓝端{blue["n02_valid"]}/17 | NOT_TESTED | NOT_TESTED | B2/*_metrics.csv |\n'
    table+=f'| 累计旋转 | C -82.2099°；W/F2全带身份不成立 | 标准+{b["rotation_deg"]:.6f}°；加密门失败，不宣称全连续带成立 | NOT_TESTED | NOT_TESTED | B2/standard_links.csv |\n'
    table+=f'| 标准唯一链接 | 历史波长集合不同 | {b["unique_main_links"]}/24；蓝端唯一16/16但可信14/16 | NOT_TESTED | NOT_TESTED | B2/*_all_edges.csv |\n'
    table+=f'| 最差/平均主盘外峰比 | 历史见原CSV | {b["min_outside_ratio"]:.6f} / {b["mean_outside_ratio"]:.6f} | NOT_TESTED | NOT_TESTED | B2/standard_metrics.csv |\n'
    table+=f'| 主瓣绝对效率（单位入瞳） | 不同几何不作公平对比 | 最低{100*b["min_main_incident_fraction"]:.3f}%；平均{100*b["mean_main_incident_fraction"]:.3f}% | NOT_TESTED | NOT_TESTED | 同上 |\n'
    table+=f'| ROI收集效率 | 历史512um窗口未过99% | {100*b["min_roi_fraction"]:.3f}–{100*b["max_roi_fraction"]:.3f}% | NOT_TESTED | NOT_TESTED | 同上 |\n'
    table+='| 数值收敛 | C条件通过、W端点失败 | G3-Numerics FAIL（边缘能量）；核心形态/位置误差较小 | NOT_TESTED | NOT_TESTED | gate3_convergence.csv |\n'
    table+='| 加工容差 | 历史非同条件 | 17组有界假设扰动已量化，实测NOT_TESTED | NOT_TESTED | NOT_TESTED | gate3_fabrication.csv |\n'
    table+=f'| 谱诊断/双孔径 | NON-FAIR REFERENCE | Gram条件数{b["gram_condition_number"]:.3g}；有效秩{b["effective_rank"]:.3f}；双孔径NOT_TESTED | NOT_TESTED | NOT_TESTED | B2/standard_gram.npz |\n'
    table+='| Gate | 只读历史 | G0/G1 PASS；G2/G3-Numerics FAIL；L1未通过 | NOT_TESTED | NOT_TESTED | gates.json |\n'
    csvwrite(out/'gate1_metrics.csv',records)
    with (out/'B2/standard_links.csv').open(encoding='utf-8-sig',newline='') as f:linkrows=list(csv.DictReader(f))
    csvwrite(out/'gate2_peak_links.csv',linkrows)
    csvwrite(out/'gate2_psf_metrics.csv',records)
    with (out/'B2/dense_blue_metrics.csv').open(encoding='utf-8-sig',newline='') as f:br=list(csv.DictReader(f))
    csvwrite(out/'gate2_dense_blue_metrics.csv',br)
    textfile(out/'gate1_summary.md',f'# G1\n\nSIMULATED PASS，标准25通道B2已通过，但不代替G2/G3。\n\n{table}')
    textfile(out/'gate2_summary.md',f'# G2\n\nSIMULATED **{G2}**。标准25通道PASS；425nm冻结定位失败，蓝端5nm为16/17；局部1nm若干角差不超过像素/拟合误差代理，未形成可信连续分支。\n\n见425nm_fit_failure.png、425nm_fit_diagnostics.csv、B2/adaptive_blue_links.csv。保留旧1.25与新1.50门，未修改冻结检测器。\n')
    gtable='| Gate | 状态 | 实际范围 |\n|---|---|---|\n'+''.join(f'| {g} | {v["status"]} | {v.get("execution","")}；{v.get("reason","")} |\n' for g,v in gates.items())
    report=f'''# N02 本轮执行与科研决策

## 1. 本轮实际执行范围

完成N02-0、N02-1A、N02-1B（25标准通道、546.1nm参考、420–500nm/5nm及421–429nm局部1nm）、N02-1C（关键数值收敛、独立实现、17组×25通道工艺/材料假设扰动、像元积分）。
    原首轮n02_20261019_01在量化测试浮点边界判断失败后停止；修正测试的整数级别核对后本轮12/12通过。首次本轮因validation模块尚未落盘、首次续跑因历史run模块名冲突、计算完成后因reporting模块尚未落盘中断；均保留原traceback与续跑记录，随后以绝对文件导入隔离并用finalize.py独立归档，未覆盖结果。没有重跑已完成标准传播。
P0实验/诊断及归档已完成，科学失败仍保留。依据任务书第14节停止条件，G3边缘门未满足后未开展P1结构扫描、低维优化、G7双孔径和G8重建。

{gtable}

## 2. 最重要的数值结果

全部为SIMULATED；材料模型为ASSUMED Cauchy n(λ_um)=1.5292+0.00800/λ_um²，非实测IP-Dip2曲线。设计546.1nm；n={float(__import__('optics').cauchy(.5461)):.12f}；p={design(config())['period_um']:.12f}um。
R500um，f20mm，物距180mm，固定探测面22.495mm。2048²输入、dx1um、padding2输出4096²、complex128精确ASM；固定512um ROI。只生成一张实体高度，10级floor量化、孔径外振幅为零。各波长高度SHA一致。
每波长原始强度、归一副本和完整面积能量见`B2/cases/*nm.npz`；逐波长指标见`B2/standard_metrics.csv`与`gate2_psf_metrics.csv`；全部候选/可行边/未匹配记录见`B2/*_all_peaks.csv`与`B2/*_all_edges.csv`。
最高相邻未去均值PSF余弦{b['max_adjacent_cosine']:.9f}，Gram有效秩{b['effective_rank']:.6f}、Gram条件数{b['gram_condition_number']:.6f}；这是强度字典诊断，不等于未知场景HSI可辨识。
主峰半径{b['min_radius_um']:.5f}–{b['max_radius_um']:.5f}um，CV={b['radius_cv']:.6f}，不是整图刚性旋转。
标准相邻角差范围{min(float(r['delta_angle_deg']) for r in linkrows):.6f}–{max(float(r['delta_angle_deg']) for r in linkrows):.6f}°；误差代理和逐段门保留原数值，不四舍五入凑PASS。

{table}

## 3. 最严重的三个风险/反例

1. **425nm冻结定位失稳**：原1um/pad2的3×3对数二次拟合诊断为`{diag[0]['diagnostic_fit_reason']}`，偏移像素={diag[0]['offset_pixels']}，原始强度仍单半峰域且峰比约{diag[0]['outside_ratio']:.6f}。这是定位/采样风险，不能冒称已观察双峰篡位。5nm蓝端16/17通过；自适应局部24/25通过且仅{adaptive['credible_links']}/24可信链接。证据`425nm_fit_failure.png`、`425nm_fit_diagnostics.csv`、`blue_peak_diagnostics.png`。
2. **有限域边缘门未满足**：420nm标准边缘份额={edge[420]:.9f}，660nm={edge[660]:.9f}，均与冻结0.001比较；padding4/细采样的失败逐项见`gate3_convergence.csv`。pad4相对pad2的ROI形态L1最大{max(r['shape_l1'] for r in convpad):.6f}，峰位差最大{max(r['peak_shift_um'] for r in convpad):.6f}um；dx0.5最大L1={max(r['shape_l1'] for r in convdx):.6f}。独立CPU精确ASM的L1最大{max(r['shape_l1'] for r in ind):.3g}，证明实现一致，不能消除两者共享的有限域风险。图`gate3_convergence_differences.png`。
3. **收集/主瓣效率与相关性风险**：420nm主盘/入瞳仅{100*records[0]['main_lobe_energy_fraction']:.4f}%，512um ROI/入瞳{100*records[0]['crop_fraction']:.4f}%；标准ROI之外能量最高{100*(1-b['min_roi_fraction']):.4f}%。所有25标准点ROI99 FAIL。相邻通道余弦最高{b['max_adjacent_cosine']:.6f}，未验证噪声下双谱/连续谱估计。假设高度缩放/圆角/横向采样造成的具体失效点均保留于17组文件，不能用ROI归一掩盖。图`B2/metrics_trajectory_gram.png`。

## 4. 可复现性

仓库HEAD `{env['git_head']}`，起始dirty全文见git_status_before.txt；本轮新增文件清单和SHA见source_hashes_final.json。历史{len(before)}文件保护核查PASS（size/mtime；文本另有SHA），未覆盖任何N00/N01结果，未提交/重置/清理Git。
Python `{env['python']}`，torch {env['torch']}，CUDA {env['cuda']}，GPU {env['gpu']}，NumPy {env['numpy']}，SciPy {env['scipy']}；未安装新依赖。种子20261019。
物理测试{sum(x['status']=='PASS' for x in tests)}/{len(tests)} PASS；独立归档回读{ncases}份NPZ PASS；最大Parseval误差{maxenergy:.3g}（包含complex64对照）。GPU已记录的最大分配显存{gpu/2**30:.3f}GiB，逐次运行时间/显存见propagation_ledger.jsonl，累计已记录传播时间{total_seconds:.2f}s（不含全部绘图、压缩、CPU审计和中断间隔，不能冒充总墙钟时长）。
复现命令（新run-id，禁止覆盖）：
```powershell
& 'D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe' -B experiments/n02/run.py --run-id n02_replay_unique
& 'D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe' -B experiments/n02/verify.py --run-id {out.name}
```
配置`configs/n02/baseline_B.yaml`，冻结协议`protocol_frozen.json`，输入哈希`input_hashes.json`，B2只读属性及SHA索引`B2/frozen_sha256.json`（误覆盖防护，不是不可变存储）。
量化、全局缩放、折射率、局部20nm平滑误差、0.5/1um圆角、2/4um横向像元化、2um遮光偏心、0.1mrad倾斜均为ASSUMED；见fabrication_assumptions.json。像元1/2/4/8um积分和Gram已计算。真实工艺、探测器MTF、吸收反射、侧壁/矢量散射NOT_TESTED。

## 5. 研究结论（Q1–Q5）

- Q1：SIMULATED 标准25通道支持低NF单阶量化DOE形成单主瓣单调轨迹；**尚未证明“仅降低NF已足够”**，因同材料同几何R严格消融未执行，且蓝端定位门失效。
- Q2：SIMULATED 固定高度、10级量化、精确ASM标准点成立；G2蓝端与G3边缘门FAIL，故完整数值收敛后的宽带可靠性**未成立**。DERIVED约244°只是先验，本轮244.849°来自真实标准PSF定位，不用于覆盖失败。
- Q3：NOT_TESTED。数值门失败后未跑硬/软消融，不能声称高斯软环带消除不连续或优于硬环带。
- Q4：SIMULATED 已观察主瓣入瞳能量最低8.36%、ROI损失最高26.39%、相邻相关性高及425nm定位脆弱；材料色散和工艺仅假设敏感性，实际加工NOT_TESTED。
- Q5：NOT_TESTED。未生成可加工双孔径整体布局，未验证独立传感器通道/相干隔离，也未做固定总光子预算互补性比较。反向手性B3与B2镜像一致仅为控制，不能据此证明额外光谱信息。

L1：未通过完整门禁。L2/L3：NOT_TESTED。低NF路线有标准离散谱点的正证据，但不足以宣称替代C型路线或双孔径HSI系统成功。

## 6. 下一步优先任务

1. 优先固定物理采样与高度，在更大可控传播域/独立开放边界参照下核查420/425/660nm边缘能量与核心PSF；不能放宽0.001门。
2. 复核425nm的冻结定位失败，并保留旧结果；若增加诊断定位器，须同时报告冻结检测口径，不能替换它获得通过。
3. 待数值证据可靠后，才开展同条件R消融、硬/软对照，再决定是否有资格做双孔径公平光子预算验证。
'''
    textfile(out/'N02_final_decision.md',report)
    textfile(out/'N02_summary_for_reviewer.md',f'# N02 复核摘要\n\n标准25点B2形态/链接PASS（{b["rotation_deg"]:.6f}°），但425nm蓝端定位FAIL、G3边缘门FAIL。L1未通过，L2/L3未测试；禁止以标准25/25替代全门禁。\n\n{gtable}\n\n{table}')
    textfile(out/'completion_summary.md',f'# 本轮完成状态\n\nP0计算、失败诊断、工艺假设量化与独立归档完成；科研G2/G3 FAIL。P1/P2按数值停止条件未执行，非已验证失败。\n\n{gtable}\n\n入口：experiments/n02/run.py；复核：experiments/n02/verify.py；总报告：N02_final_decision.md。\n')
    reportdir=ROOT/'reports/n02'/out.name;reportdir.mkdir(parents=True,exist_ok=False)
    for name in ['N02_final_decision.md','N02_summary_for_reviewer.md','completion_summary.md','N02-0_repository_audit.md','N02-0_physics_audit.md','gate1_summary.md','gate2_summary.md','gate3_convergence.md','gate3_fabrication_tolerance.md']:
        textfile(reportdir/name,(out/name).read_text(encoding='utf-8'))
    # 完整哈希清单最后生成，不包含清单自身；记录技术中断，不把它抹成一次无失败运行。
    hashes={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
    write(out/'artifact_manifest.json',hashes)
    write(out/'manifest.json',dict(status='COMPLETE_WITH_SCIENTIFIC_FAILURES',time=now(),git_head=env['git_head'],
       git_dirty=True,entry='experiments/n02/run.py',invocation=read(out/'invocation.json'),
       config=read(out/'config_resolved.json'),material_source='任务书给定Cauchy近似；ASSUMED，外部DOI读取失败，未核验IP-Dip2实测曲线',
       environment=env,seed=20261019,source_hashes=source_hash,artifact_manifest_sha256=sha(out/'artifact_manifest.json'),
       input_hashes_sha256=sha(out/'input_hashes.json'),gates=gates,verified_cases=ncases,
       technical_failures=[str(p.relative_to(out)) for p in out.glob('*traceback*')],
       approximations=['标量薄相位','ASSUMED材料/工艺','Fresnel对照为近轴近似','理想方形像元积分，无实测MTF'],
       resource=dict(peak_gpu_allocated_bytes=gpu,recorded_propagation_seconds=total_seconds,
           full_wall_seconds=None,reason='真实执行含中断与续跑，保留逐条时间戳，不猜测净墙钟')))
    print('N02归档完成：',out,flush=True)
