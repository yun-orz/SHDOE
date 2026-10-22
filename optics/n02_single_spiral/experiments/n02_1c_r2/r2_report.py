"""机制审计结案及完整追溯归档，科学局部证据不替代全域Gate。"""
from r2_common import *


def finalize(out,cfg,env,resource,p1,p1analysis,p2,p2analysis,started):
    decision,conv,comparisons,labels=p1analysis
    tests=read(out/'implementation_tests.json');original=read(OLD/'gates.json')
    # 汇总必须保留三类证据，旧边缘份额只回读，不从稀疏点重构。
    oldmetrics=[]
    for pad,path in [(2,OLD/'B2/cases/420nm.npz'),(4,OLD/'convergence/cases/pad4_420nm.npz')]:
        _,_,r=loadcase(path)
        oldmetrics.append(dict(scope='frozen_original',wavelength_nm=420,metric='boundary_share_16um',padding=pad,
            value=r['edge_fraction'],numerator='全传播域四边16um条带，角点只计一次',denominator='有限周期传播域总能量',
            physical_domain_um=2048*pad,ROI_energy_incident=r['crop_energy'],finite_domain_energy=r['raw_energy'],
            source_file_sha256=sha(path),legacy_edge_limit=.001,legacy_G3='FAIL'))
    metrics=oldmetrics.copy()
    for r in comparisons:metrics.append(dict(scope='parallel_diagnostic',wavelength_nm=420,metric='selected_ASM_vs_RS_complex_residual',
        point_id=r['point_id'],padding=r['ASM_padding'],value=r['relative_complex_residual'],
        reference_scope='physical_reference',reference_q=r['RS_best_q'],no_full_edge_integral=True))
    for r in p1['rows']:metrics.append(dict(scope='physical_reference',wavelength_nm=420,metric='RS_point_intensity',
        point_id=r['point_id'],input_q=r['input_q'],value=r['intensity_raw'],no_full_edge_integral=True))
    if p2analysis['status']!='NOT_RUN_RESOURCE_LIMIT':
        for r in csvread(out/'peak_mask_sensitivity_rs.csv'):
            metrics.append(dict(scope=r['scope'],wavelength_nm=546.1,metric='outside_ratio_or_restricted_candidate_ratio',
                method=r['method'],mode=r['mode'],value=float(r['outside_ratio']),ratio_scope=r['ratio_scope']))
    csvwrite(out/'metrics_old_parallel_reference.csv',metrics)
    localconverged=decision['quadrature_4to8_converged'];q48=decision['quadrature_4to8_tested']
    alltests=all(r['status']=='PASS' for r in tests)
    stage_complete=p1['status']=='COMPLETE'
    overall='INCONCLUSIVE' if decision['label']=='INCONCLUSIVE' or not stage_complete else 'LOCAL_MECHANISM_SUPPORTED_GLOBAL_INCONCLUSIVE'
    final=dict(stage='N02-1C-R2',execution_status='COMPLETED_LOCAL_DIAGNOSTIC' if stage_complete else 'PARTIAL_RESOURCE_LIMIT',
        scientific_status=overall,boundary_label=decision['label'],local_label_counts=decision['local_label_counts'],
        P1_quadrature_levels_done=read(out/'P1_execution_status.json').get('RS_q_done',[]),P2=p2analysis,
        P3='评价器不稳定有证据，单圈物理模态尚未完全认证',
        historical_states=dict(G0='PASS_SIMULATED_FROZEN',G1='PASS_SIMULATED_FROZEN',G2='FAIL',G3_Numerics='FAIL',
          G3_Fabrication='仅假设扰动实验完成，真实工艺NOT_TESTED',G4_G8='NOT_TESTED',prior_P0B='INCONCLUSIVE'),
        retrospective_gate_override=False,full_boundary_edge_estimated=False,full_ROI_physical_ratio_certified=False,
        G4_G8_permission=False,next_experiment='仅在420nm同一8个预注册边界点追加16x16源像元内RS中点求积，与8x8比较，或对同一分片常值源做有误差界的像元相位积分；先排除尚未收敛的输入求积，不扩谱、不重新设计。')
    write(out/'decision.json',final)
    p1text=f'''# 420nm边界机制审计

分类：**{decision['label']}**。执行状态：{p1['status']}。物理参考为固定原像元高度/掩模的RS面积求积，不重新设计、不重取模。
预注册{len(p1['plan'])}个点，含四边法向、沿边、近角点、内外与中心/主峰控制；几何反向点不意味着实际螺旋PSF强度相等。
1x1/2x2/4x4逐像元中点面积积分，8x8仅预注册8个法向点。各级共用K，不把输出或入瞳强行重新归一。复场全部移除同一exp(ikz)，强度单位为um^-2/原单位入瞳参考。
4→8共{q48}点，诊断尺度复场≤1%、强度≤2%下通过{localconverged}点，最大相对复场变化={decision['max_4to8_complex_change']}，最大强度变化={decision['max_4to8_intensity_change']}。
局部标签计数：{decision['local_label_counts']}。若求积未收敛，不能把ASM与RS的残差全归因为周期复制，也不能把单点RS非零直接认证成可靠物理尾。
ASM对照只做pad2/pad4频谱的选点逆DFT，不产生全域新强度图；与原完整FFT的ROI控制点比较见raw/P1_ASM_pad*_selected.npz元数据。此方法与相同离散周期ASM严格等价，不是非周期参考。
冻结420nm边界份额：pad2={oldmetrics[0]['value']:.12f}、pad4={oldmetrics[1]['value']:.12f}；ROI/入瞳分别={oldmetrics[0]['ROI_energy_incident']:.12f}/{oldmetrics[1]['ROI_energy_incident']:.12f}，不能混为边缘份额。
边界数组区域：top=I[:b,:]，bottom=I[-b:,:]，left=I[b:-b,:b]，right=I[b:-b,-b:]，b=16/dx；四项乘dx²相加，分母Σ全域I dx²。pad2宽4096um，pad4宽8192um；ROI恒512um。
outside pad2点的ASM按周期延拓求值，已标记，不当作原传感器域内实测。几何对边不对称是螺旋PSF允许的物理行为，不能仅凭不等判伪影。
**本轮没有受控全条带面积积分或误差界，不估算edge_fraction，不将任何局部结果写成G3 PASS。** 原0.001和0.1门完全保留。
'''
    textfile(out/'N02_boundary_mechanism.md',p1text)
    if p2analysis['status']!='NOT_RUN_RESOURCE_LIMIT':
        textfile(out/'N02_peak_ratio_mechanism.md',f'''# 546.1nm局部峰比与掩模机制

P2执行完成；物理全ROI验收仍INCONCLUSIVE，旧G3 FAIL不变。
完整定义见peak_ratio_definitions.json。原分子为ROI最大像素强度；原分母为离各自3x3拟合中心严格大于1.22lambda*z/D的所有ROI像素的最大值，不要求分母点是独立局部旁峰。distinct_side_ratio是另一候选定义。
三列证据并排：frozen_original是各自旧中心与原生网格；parallel_diagnostic是共同物理中心、旧细图2x2面积对齐；physical_reference是同一原高度分片常值的1/2/4输入求积与固定少量候选输出。
本轮RS候选集合1x1至4x4的局部峰比绝对变化={p2analysis['RS_q1_q4_local_candidate_ratio_difference']:.12g}；坐标、分子/分母强度均在peak_mask_sensitivity_rs.csv中，不把旧0.298764等数值冒充本轮物理差。
新RS始终固定共同中心，不在每级重新拟合取得更好结果。候选是否从盘内变盘外取决于几何与原网格，不是新生物理旁瓣，见peak_candidate_geometry.csv。
统一输出像元面积求积状态={p2analysis['output_area_done']}；仅2x2中点近似，另列中心判外与物理半径裁切后的盘外面积均值。两者定义不同，不混用；输出求积收敛、完整ROI最大值和8x8源输入均NOT_TESTED。
因此本轮可分析掩模/采样敏感性及固定局部主/旁峰的输入求积影响，不能给真实全局峰比或冻结0.1门授予通过。
''')
    history_before=read(out/'preservation_before.json');after=snapshot();changed=[p for p,v in history_before.items() if p not in after or after[p]!=v]
    assert not changed,changed
    for p,digest in read(out/'input_hashes.json').items():assert sha(p)==digest,f'冻结输入变化：{p}'
    write(out/'preservation_verification.json',dict(status='PASS',old_files_checked=len(history_before),changed_original_files=changed,
       scope='全部旧文件size/mtime及文本SHA；本轮用到的二进制输入另完整SHA，不冒称所有旧二进制重哈希'))
    ledger=[json.loads(line) for line in (out/'execution_ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    peakgpu=max((r.get('gpu_peak_allocated_bytes') or 0 for r in ledger),default=0);mem=memory()
    resources=dict(wall_seconds=time.perf_counter()-started,cpu_peak_working_set_bytes=mem['cpu_peak_working_set_bytes'],
       max_recorded_gpu_allocation_bytes=peakgpu,RS_device=resource['RS_device'],source_chunk=8192,point_chunk=4,
       new_full_domain_output_ASM=0,selected_periodic_ASM_pads=sorted(p1['asm']),no_pad5_pad8=True,resource_after=mem)
    write(out/'resource_usage.json',resources)
    summary=f'''# N02-1C-R2 最终审计

## 1. 执行范围与结论

只执行P0–P4机制审计；执行状态={final['execution_status']}，科研判定 **{overall}**，边界机制标签 **{decision['label']}**。
初次n02_1cr2_20261020_01因完成日志重复padding字段中断，物理数组与异常堆栈、8份原始源码快照完整保留；修正仅涉及日志调用，此后唯一新run重跑，未覆盖失败样本。
P1优先420nm、原B2高度不变，共{len(p1['plan'])}个预注册点，源1/2/4输入求积；8x8为固定8点。P2={p2analysis['status']}；P3仅回读425nm，不新增该波长传播。
旧G0/G1 PASS、G2/G3-Numerics FAIL、工艺仅假设扰动实验完成、G4–G8 NOT_TESTED、上轮P0B INCONCLUSIVE全部保持。没有新DOE、优化、双孔径或HSI重建。

## 2. P1：边界成对点与输入求积

4→8源求积{q48}个点，复场≤1%且强度≤2%的诊断尺度通过{localconverged}个；最大复场变化{decision['max_4to8_complex_change']}、最大强度变化{decision['max_4to8_intensity_change']}。
结果逐点保留，不选最优样本代替全体；缺失8级记录为预注册子集未安排/资源限制。原始复场及固定K、各级入瞳能量见raw/P1_RS_q*.npz和boundary_pointwise_rs.csv。
稀疏成对点标签：{decision['local_label_counts']}。本轮没有把点位乘面积来估计整条带edge_fraction。
周期ASM对照pads={sorted(p1['asm'])}，用GPU FFT谱+分块精确核+选点逆DFT，未保存或生成整域传播强度。相同物理点复场、强度、相位差及原ROI控制核对见boundary_asm_rs_comparison.csv与raw元数据。
原冻结pad2/pad4边界份额{oldmetrics[0]['value']:.12f}/{oldmetrics[1]['value']:.12f}属于四边16um条带/有限域总量，不是ROI边缘或环绕误差直接测量。原0.001门与主盘外峰比差0.1门均未改变。
若4→8尚不满足诊断收敛，周期与输入采样贡献不能可靠拆开；即使个别点稳定，也不代表全条带或25+加密波长通过。

## 3. P2：546.1nm固定主盘中心诊断

{p2analysis}
原完整旧图三口径与新局部RS在peak_mask_sensitivity_rs.csv分列；物理共同中心、主/旁候选坐标及掩模半径先于计算冻结。新输入像元高度不插值、不量化；旧dx0.5图属于历史重新采样高度，不能当本轮同高度独立物理真值。
完整分子/分母与候选集定义见peak_ratio_definitions.json。新RS局部比不等于全ROI盘外最大值；输出像元面积2x2并未取得输出求积收敛证书，禁止以共同掩模差变小给旧G3改判。

## 4. P3：425nm证据保留

**评价器不稳定有证据，单圈物理模态尚未完全认证**。独立从原NPZ重算Hessian与偏移、同一49点RS误差，实际5nm pad4间隔核查通过，详见425_evaluator_evidence_check.md/json。没有新全带证据，旧G2仍FAIL。

## 5. 数值模型、自测与资源

高度原文件SHA={sha(OLD/'B2/height_um.npy')}，固定原1um源像元分片常值；孔径mask亦在原像元内保持二值常量，不在亚像元重裁圆孔。球面入射振幅/曲率与RS法向因子在子点实际坐标计算，子面积1/q² um²，全部求积共用原入瞳K。
RS1复核包括小方孔轴上解析幅值、对称瞳孔复场对称、CPU/GPU及不同分块、独立NumPy子像元循环；选点ASM另与完整小网格IFFT核对。实现自测{sum(r['status']=='PASS' for r in tests)}/{len(tests)} PASS。
环境：{env['python']}；torch {env['torch']}，CUDA {env['cuda']}，GPU {env['gpu']}，NumPy {env['numpy']}，SciPy {env['scipy']}。未安装依赖。HEAD={env['git_head']}，dirty见git_dirty_before.txt。
预检见resource_preflight.json；执行墙钟{resources['wall_seconds']:.2f}s，CPU本进程峰值工作集{resources['cpu_peak_working_set_bytes']/2**30:.3f}GiB，记录的最大GPU分配{peakgpu/2**30:.3f}GiB。RS按8192源像元×4输出点分块；未跑pad5/pad8或全波段传播。
历史{len(history_before)}文件保护核查PASS；使用的历史二进制及报告/协议输入SHA见input_hashes.json，新增源码见source_hashes.json，全部输出SHA见artifact_manifest.json。全过程未覆盖/删除历史产物，未安装、提交或清理Git。

## 6. 下一项最低资源实验与停止位置

{final['next_experiment']}
当前只结案于机制归因和下一轮决策。即使局部证据支持周期污染或掩模敏感性，也须未来独立新run取得受控全边界证据、全部25+加密波长及完整硬门验收后，才可申请重新冻结；本轮不自动恢复G4–G8。

## 可复现命令

```powershell
& '{env['python']}' -B experiments/n02_1c_r2/r2_run.py --run-id n02_1cr2_replay_unique
& '{env['python']}' -B experiments/n02_1c_r2/r2_verify.py --run-id {out.name}
```
唯一run目录拒绝覆盖。配置configs/n02_1c_r2/protocol_v1.json；点位与协议在计算前落盘，见preregistration.json。
'''
    textfile(out/'N02_1CR2_final_audit.md',summary)
    textfile(out/'N02_1CR2_next_step_decision.md',f"# 下一阶段入口\n\n科研判定：{overall}；本轮不恢复G4–G8。\n\n{final['next_experiment']}\n\n局部点求积不等于全域边缘份额，所有旧Gate与上轮P0B标签均保留。\n")
    report=ROOT/'reports/n02_1c_r2'/out.name;report.mkdir(parents=True,exist_ok=False)
    textfile(report/'N02_1CR2_final_audit.md',summary)
    textfile(report/'N02_1CR2_next_step_decision.md',(out/'N02_1CR2_next_step_decision.md').read_text(encoding='utf-8'))
    # 先独立重算原始局部场/误差表，再封存，工程通过不覆盖科学未决。
    from r2_verify import numerical_verify
    verified=numerical_verify(out)
    write(out/'verification.json',dict(status='PASS',tests_pass=alltests,numerical=verified,old_files_unchanged=True,
       old_G2_G3='FAIL_UNCHANGED',scientific_status=overall,scope='局部原始复场、强度、求积差、配对与协议哈希，不宣称全域收敛'))
    outputs={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    write(out/'artifact_manifest.json',outputs)
    write(out/'manifest.json',dict(status=final['execution_status'],scientific_status=overall,time=now(),decision=final,
       environment=env,resource_usage=resources,protocol_sha256=sha(out/'protocol_locked.json'),
       input_hashes_sha256=sha(out/'input_hashes.json'),source_hashes=read(out/'source_hashes.json'),
       artifact_manifest_sha256=sha(out/'artifact_manifest.json'),entry='experiments/n02_1c_r2/r2_run.py'))
    print('R2归档完成',overall,out,flush=True)
