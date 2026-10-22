"""本轮独立决策与证据归档；不改写原Gate。"""
from p0b_common import *


def finalize(out,env,analysis_a,analysis_c,b_data,started):
    arows,uncertainty,fit425=analysis_a;energy,pixels,grams=analysis_c
    sources,references,domain,comp,ratios,rs,trajectories=b_data
    tests=read(out/'diagnostics/implementation_self_tests.json')
    rechecked=read(out/'diagnostics/legacy_numbers_rechecked.json');required=read(out/'diagnostics/legacy_convergence_count.json')
    frozen=[r for r in arows if r['locator']=='frozen3'];bad_steps=[r for r in frozen if r['scaled_04_18_gate'] is False]
    shapes=csvread(out/'diagnostics/blue_1nm_shape.csv')
    minratio=min(float(r['strongest_competitor_ratio']) for r in shapes)
    maxcompetitor=max(float(r['strongest_competitor_ratio']) for r in shapes)
    stable_shape=all(int(r['halfmax_components'])==1 for r in shapes) and maxcompetitor<1/1.5
    A='EVALUATOR_INSTABILITY' if stable_shape and fit425[0]['failure_reason']=='OFFSET_EXCEEDS_ONE_PIXEL' else 'INCONCLUSIVE'
    B='INCONCLUSIVE'
    # 本轮开放参考只核查局部RS，未认证全边界积分/原像元内部求积，故不自动解决全部前向问题。
    overall='INCONCLUSIVE'
    g=grams[0];p0b=dict(status=overall,stage='N02-1C-R',time=now(),work_A=A,work_B=B,
        work_C='DIAGNOSTIC_RECOMPUTATION_COMPLETED',legacy_G2='FAIL',legacy_G3_Numerics='FAIL',
        G4_G8='NOT_TESTED_DO_NOT_START',physical_failure_established=False,
        reasons=['425nm冻结拟合失败可复现，负定曲面弱曲率方向使驻点超1pixel；未观察双半峰域篡位',
          '边界份额包含物理尾部和周期/采样效应；稀疏开放RS核查不等于全边界能量参考',
          '旧660nm pad4和546.1nm dx0.5主盘外峰比另超0.1，需保留原失败',
          'dx0.5旧对照同时重采样量化高度与探测面，不能把差异全部归因定位器'],
        next_minimal_experiment='只在546.1nm，将冻结1um B2高度解释为分片常值，对同一局部主/旁峰及主盘边缘坐标进行2x2/4x4像元内RS中点求积；固定同一主盘中心并并列冻结输出，以区分输入求积误差与主盘掩模敏感性。不得由此自动启动G4–G8。')
    write(out/'P0B_gate_decision.json',p0b)
    write(out/'diagnostics/work_A_decision.json',dict(classification=A,
        positive_evidence=dict(fit_offset=fit425[0]['unconstrained_offset_pixels'],hessian_eigenvalues=fit425[0]['hessian_eigenvalues'],
            hessian_condition=fit425[0]['hessian_condition'],raw_halfmax_unique=stable_shape,max_competitor_relative_height=maxcompetitor),
        counterevidence=['多个估计器受局部不对称和像素相位影响；约束或插值不会保证无偏',
           '局部11点和有限候选链接不能严格证明全波段同一物理模态','原1nm角差门有多个失败，不只425nm单点'],
        old_G2='FAIL'))
    # 并列旧与新口径全部必要点，不省略无效冻结输出。
    parallel=[]
    for r in trajectories:
        w=r['wavelength_nm'];oldraw,oldc,oldrec=loadcase(OLD/'B2/cases'/f'{w:g}nm.npz')
        parallel.append(dict(**r,old_frozen_n01_status=oldrec['n01_status'],old_frozen_angle_deg=oldrec['raw_angle_deg'],
            old_G2='FAIL',new_diagnostic_protocol='N02-1C-R-P0B-v1',formal_new_gate='NOT_GRANTED'))
    csvwrite(out/'diagnostics/old_new_parallel_comparison.csv',parallel)
    atext=f'''# 蓝端分支与定位审计

分类：**{A}**；旧G2永久保留FAIL。
425nm主峰argmax=(13.5,-21.5)um，冻结Hessian特征值{fit425[0]['hessian_eigenvalues']}，条件数{fit425[0]['hessian_condition']:.6f}。
梯度{fit425[0]['gradient']}，无约束驻点偏移{fit425[0]['unconstrained_offset_pixels']}pixel，RMSE={fit425[0]['rmse_log']:.12g}。
曲面为负定且非奇异，驻点超出拟合中心一像素门；不能解释为Hessian非负，也不是对数截零（clip样本={fit425[0]['clipped_log_samples']}）。
局部离散最大格点与最小二乘曲面最大值并不必然一致。3x3窗口拟合存在非二次残差；弱曲率方向把梯度扰动放大为较大驻点偏移。真实PSF局部不对称、网格取样和周期域微小扰动可共同改变拟合；条件数{fit425[0]['hessian_condition']:.3f}不支持单凭“严重病态矩阵”解释。
原pad4及dx0.5的冻结H/偏移均与旧CSV在1e-12容差内复现，见425_fit_audit.csv。
420–430nm半峰连通域全部为1，最强独立旁峰相对主峰最高{maxcompetitor:.6f}，没有接近0.8门的竞争证据。它支持评价器/数值耦合解释，不是物理双峰篡位证据。
原冻结1nm角差越界的终点波长：{[r['wavelength_nm'] for r in bad_steps]}；全部数值见blue_1nm_trajectory_comparison.csv、blue_domains_trajectory.csv。
6种定位器并行输出；约束5/7中心限制±1pixel，必须查看边界活跃；插值1/3阶不代表独立光学模型。局部插值前后积分差、负值、8方向初值离散均保存，没有强行缩放守恒。
位置至角度不确定度仅为估计器协方差的切向投影；它不是统计σ标定或置信区间，有限差分未过代理门不能自动证明真实反转。
合成8类单峰/细长峰/非对称肩峰/双峰/噪声测试见locator_synthetic_tests.json，含已知真实极值位置；约束法限幅不等于准确。
反证与限制：多估计器仍可能共享取样偏差，旧P3最多12候选且曾有截断敏感历史，局部11点不能严格证明所有λ下同一模态。若后续独立开放积分出现两条相当强的独立局部峰，再重新评估PHYSICAL_BRANCH_AMBIGUITY/BOTH。
'''
    textfile(out/'diagnostics/blue_branch_identity.md',atext)
    corestats={method:max(r['core49_relative_L1'] for r in rs if r['method']==method) for method in sorted(set(r['method'] for r in rs))}
    domaintext=f'''# 边界与光能闭合结论

工作包B：**INCONCLUSIVE**；旧G3-Numerics继续FAIL。
新增传播全部加载同一B2高度SHA={arrsha(np.load(OLD/'B2/height_um.npy'))}；没有跨波长设计/包裹，没有频域滤波、吸收边界或窗函数。
原检查{required['required']}条必需比较中{required['fail']} FAIL/{required['passed']} PASS。不能仅凭候选pad4边界低于0.001改写组合门。
660nm pad4主盘外峰比差0.10349、546.1nm dx0.5差0.29876超过原0.1；见legacy_convergence_failure_breakdown.csv和ratio_sensitivity_decomposition.csv。
Parseval在周期DFT模型内检验离散能量闭合；高精度接近1不表示无限平面内的能量全在有限物理窗口，也不证明没有环绕。
domain_sweep.csv固定512um ROI并列全域尺寸与绝对ROI能量，记录候选/基线/组合边界门。边界份额分子所处位置及面积随D变化，不能把下降率直接当误差收敛阶。
非周期Fresnel积分使用二维可分离CZT计算有限入瞳积分，不是FFT周期传递函数；全ROI报告近轴四次相位上界，不把近轴结果当精确答案。
非同源RS参考保留exp(ikR)/R核及1+i/(kR)项，直接对已采样入瞳中点求和，省略强度无关全局活塞。49个原生坐标局部点对RS的最坏相对L1：{corestats}。
425nm另算13x13、0.25um步长的RS局部阵列。远端稀疏点仅机制证据；超过0.45cycle/um标记输入求积Nyquist接近风险，不能用它估算整条边界积分。
两种解释未被完全排除：物理长衍射尾在开放空间确可非零；周期延拓/角谱传递函数采样也可在相同位置引入附加纹理。RS稀疏点和近轴ROI参考不足以认证全域16um条带的真实能量。
旧dx0.5不是相同高度数组：连续解析设计重采样后量化，边缘分数填充亦变化。共同中心、同网格积分比率仅诊断分解，不改变冻结门。
阈值0.0005/0.001/0.002敏感性全表保留，正式门仍0.001。工艺标签原SIMULATED_ASSUMED PASS只指已做17组实验，其中6组未保持25/25；本轮未升级为制造鲁棒性通过。

## 理论依据与证据等级

DERIVED：Fresnel核exp[iπ((x-x')²+(y-y')²)/(λz)]/(iλz)；RS1核z exp(ikR)(1+i/(kR))/(iλR²)。本轮的正负号、面积及CZT求值由小网格显式双矩阵、Parseval和小NA极限测试交叉核查。
文献线索：[Matsushima与Shimobaba原始论文](https://kansai-u.repo.nii.ac.jp/record/11127/files/KU-1100-20091015-50.pdf)讨论角谱传递函数采样问题；[KIT课程讲义](https://www.tfp.kit.edu/downloads/lehre_2012_ss/script_part5.pdf)给出RS/Fresnel公式。搜索摘要可见，全文读取分别429/超时，未宣称完整核验原文；全部本轮定量结论来自实际计算而非文献预期。
'''
    textfile(out/'diagnostics/energy_conservation.md',domaintext)
    write(out/'diagnostics/work_B_decision.json',dict(classification=B,core_error_vs_RS=corestats,
        physical_tail_not_excluded=True,numerical_boundary_not_excluded=True,
        limits=['非周期精确RS仅局部点，不是全条带面积积分','原像元内部波前求积未细分收敛','细采样主盘外峰比敏感性尚未完全分离']))
    failures=[r for r in read(OLD/'gate3_fabrication.json') if r['n02_valid']<25]
    write(out/'diagnostics/fabrication_label_clarification.json',dict(old_label='PASS/SIMULATED_ASSUMED',
         meaning='只确认实验已完成，不确认全部扰动合格',groups=17,groups_not_25_of_25=len(failures),
         failed_groups=[dict(name=r['candidate_id'],valid=r['n02_valid'],failed_wavelengths_nm=r['failure_wavelengths_nm']) for r in failures]))
    before=read(out/'preservation_before.json');after=snapshot();changed=[k for k,v in before.items() if k not in after or v!=after[k]]
    write(out/'preservation_after.json',after)
    assert not changed,changed
    for path,digest in read(out/'input_hashes.json').items():assert sha(path)==digest,f'输入发生变化：{path}'
    write(out/'preservation_verification.json',dict(status='PASS',historical_files_checked=len(before),changed_original_files=changed,
       input_content_hashes_checked=len(read(out/'input_hashes.json')),old_gates_sha256=sha(OLD/'gates.json'),
       scope='全部旧工程文件size/mtime和文本SHA；本轮使用的旧原始产物另完整SHA；没有声称所有历史二进制重哈希'))
    ledger=[json.loads(s) for s in (out/'execution_ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    calls=[r for r in ledger if r['event']=='ASM_COMPLETE'];rs_calls=[r for r in ledger if r['event']=='RS_DIRECT_COMPLETE']
    mem=memory();wall=time.perf_counter()-started
    resource=dict(wall_seconds=wall,cpu_peak_working_set_bytes=mem['cpu_peak_working_set_bytes'],
       gpu_peak_allocated_bytes=max((r['gpu_peak_bytes'] for r in calls),default=0),new_ASM_calls=len(calls),
       new_Fresnel_calls=sum(r['event']=='OPEN_FRESNEL_COMPLETE' for r in ledger),new_RS_calls=len(rs_calls),
       original_data_reuse=True,no_install=True,resource_after=mem)
    write(out/'resource_usage.json',resource)
    summary=f'''# N02-1C-R 执行总结

## 1. 实际范围与决策

只执行A1–A3、B1–B3和C。P0B判定：**INCONCLUSIVE**；A={A}，B={B}，C独立口径复核完成。没有启动G4/G5/G6/G7/G8，没有新DOE、软环带、训练或场景重建。
旧G0/G1 PASS、G2 FAIL、G3-Numerics FAIL、工艺SIMULATED_ASSUMED完成标签、G4–G8 NOT_TESTED全部保持，未回写任何旧文件。旧571 NPZ重新回读，900个冻结产物逐一SHA核对；旧PASS不是仅从gates.json固定标签推断。

## 2. A：425nm与蓝端

独立复现425nm冻结Hessian={fit425[0]['hessian_eigenvalues']}、驻点偏移={fit425[0]['unconstrained_offset_pixels']}pixel、条件数={fit425[0]['hessian_condition']:.6f}。负定而偏移超门，clip样本0；不是Hessian非负，也不能自动说双峰篡位。
420–430nm/1nm的原始PSF均一个半峰连通域；冻结1nm角差多个区间仍超0.4–1.8°，见blue_1nm_trajectory_comparison.csv。6定位器、8类合成峰测试、pad4/开放Fresnel轨迹及425nm开放RS子网格均已保存。
局部非二次性、弱曲率和数值域改变支持EVALUATOR_INSTABILITY。估计器离散度只作角度误差代理，不能把微分波动直接等同真实旋转回折。反证：局部11点不证明全带唯一物理模态，限制见blue_branch_identity.md。

## 3. B：边界与非边缘失败

旧edge_fraction为整个传播域四边16um条带/有限域总能量，**不是ROI边缘，也不是FFT环绕误差直接测量**。条带求和区域与面积定义见boundary_metric_definition.md。
原必需比较{required['required']}条，{required['fail']} FAIL/{required['passed']} PASS；除边界门，还有660nm pad4峰比差0.10349和546.1nm dx0.5差0.29876超0.1。原checks.edge取候选/旧基线最大值，本轮逐列分开，未改变门槛。
新增ASM {len(calls)}次，均在420、421–429、546.1、660nm允许集合及资源预算内；4096um/pad2、8192um/pad4、10240um/pad5始终比较同512um ROI。未运行预算不允许的更大网格。
非周期Fresnel-CZT与局部RS为非同源边界参照，精度测试见implementation_self_tests.json；局部RS对各模型误差见RS_core_error_summary.csv。物理长尾与数值周期/采样效应未完全分离，仍INCONCLUSIVE；不能说加padding已经解决全部G3问题。

## 4. C：光能、像元和Gram

25标准通道独立回算：ROI/入瞳{100*rechecked['roi_min']:.6f}–{100*rechecked['roi_max']:.6f}%，主盘/入瞳最低{100*rechecked['main_min']:.6f}%。所有ROI归一化副本仅用于形态，不冒充绝对效率。
理想1/2/4/8um像元100次面积积分保持能量，峰半径、位置及谱相关性见pixel_integration_effect.csv。未使用真实MTF/噪声/吸收反射数据。
L2列归一强度Gram独立重建，条件数={g['gram_condition']:.9f}，熵有效秩={g['effective_rank']:.9f}，代数秩={g['rank_at_eps_n_lambda_max']}；SVD独立复核。光子权重后条件数={g['photon_weighted_gram_condition']:.9f}、有效秩={g['photon_weighted_effective_rank']:.9f}，权重仅是假设纯谱收集数的字典诊断，不是HSI成绩或双孔径必败证据。
原17组工艺假设扰动有{len(failures)}组未保持25/25；原PASS只能解读为实验完成，不等于工艺鲁棒性合格。

## 5. 可复现性、版本与资源

仓库HEAD={env['git_head']}，起始dirty清单见git_status_before.txt；代码仅新增experiments/n02_1c_r、configs/n02_1c_r，结果和报告使用唯一新run-id。
Python={env['python']}；torch={env['torch']}，CUDA={env['cuda']}，GPU={env['gpu']}，NumPy={env['numpy']}，SciPy={env['scipy']}，随机种子20261020。未安装依赖。
{len(tests)}项独立实现自测全部PASS。历史{len(before)}文件保护PASS；完整输入SHA见input_hashes.json，代码版本见source_hashes.json，产物SHA见artifact_manifest.json；旧Gate SHA={sha(OLD/'gates.json')}。
CPU本进程峰值工作集={resource['cpu_peak_working_set_bytes']/2**30:.3f}GiB，GPU新ASM分配峰值={resource['gpu_peak_allocated_bytes']/2**30:.3f}GiB，本轮墙钟={wall:.2f}s。资源预检、调用清单及逐次运行时间见resource_preflight.json、execution_ledger.jsonl、resource_usage.json。
完整命令（运行前处于仓库根；新run-id不可复用）：
```powershell
& '{env['python']}' -B experiments/n02_1c_r/p0b_run.py --run-id n02_1cr_replay_unique
& '{env['python']}' -B experiments/n02_1c_r/p0b_verify.py --run-id {out.name}
```
P0B_diagnostic_protocol.json在新传播前冻结，旧新口径全部并列old_new_parallel_comparison.csv；约束/插值/开放参考均未替换原评价器。坐标x右y上、长度um、波长nm、距离mm、强度um^-2/单位入瞳。

## 6. 未测试项及下一项最小实验

未认证原1um像元内部传播积分收敛，未获得全开放RS边界条带面积积分，未分离旧dx0.5重新量化与探测盘取样的全部影响；未做真实材料/工艺/MTF/噪声标定。没有新门禁PASS。
{p0b['next_minimal_experiment']}
该实验针对目前最大的非边缘反例，能以单波长固定高度区分“输入求积/量化边缘”与“主盘定义/采样”两种假设。未经后续明确授权，不恢复G4–G8。
'''
    textfile(out/'summary.md',summary)
    reportdir=ROOT/'reports/n02_1c_r'/out.name;reportdir.mkdir(parents=True,exist_ok=False)
    textfile(reportdir/'summary.md',summary);write(reportdir/'P0B_gate_decision.json',p0b)
    source={p.relative_to(ROOT).as_posix():sha(p) for p in CODE.glob('*.py')}
    source['configs/n02_1c_r/P0B_protocol_v1.json']=sha(ROOT/'configs/n02_1c_r/P0B_protocol_v1.json')
    write(out/'source_hashes.json',source)
    outputs={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    write(out/'artifact_manifest.json',outputs)
    write(out/'manifest.json',dict(status='COMPLETE_DIAGNOSTIC_INCONCLUSIVE',time=now(),run_id=out.name,
        stage='N02-1C-R',entry='experiments/n02_1c_r/p0b_run.py',invocation=read(out/'invocation.json'),
        environment=env,source_hashes=source,artifact_manifest_sha256=sha(out/'artifact_manifest.json'),
        old_run=OLD,old_G2='FAIL',old_G3='FAIL',input_hashes_sha256=sha(out/'input_hashes.json'),decision=p0b,resources=resource))
    print('P0B 归档完成',out,'判定',overall,flush=True)
