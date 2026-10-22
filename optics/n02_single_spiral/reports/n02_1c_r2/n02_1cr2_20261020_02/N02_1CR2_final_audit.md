# N02-1C-R2 最终审计

## 1. 执行范围与结论

只执行P0–P4机制审计；执行状态=COMPLETED_LOCAL_DIAGNOSTIC，科研判定 **LOCAL_MECHANISM_SUPPORTED_GLOBAL_INCONCLUSIVE**，边界机制标签 **MIXED**。
初次n02_1cr2_20261020_01因完成日志重复padding字段中断，物理数组与异常堆栈、8份原始源码快照完整保留；修正仅涉及日志调用，此后唯一新run重跑，未覆盖失败样本。
P1优先420nm、原B2高度不变，共42个预注册点，源1/2/4输入求积；8x8为固定8点。P2=COMPLETED_LOCAL_DIAGNOSTIC；P3仅回读425nm，不新增该波长传播。
旧G0/G1 PASS、G2/G3-Numerics FAIL、工艺仅假设扰动实验完成、G4–G8 NOT_TESTED、上轮P0B INCONCLUSIVE全部保持。没有新DOE、优化、双孔径或HSI重建。

## 2. P1：边界成对点与输入求积

4→8源求积8个点，复场≤1%且强度≤2%的诊断尺度通过8个；最大复场变化0.006605312564243643、最大强度变化0.012598466448816955。
结果逐点保留，不选最优样本代替全体；缺失8级记录为预注册子集未安排/资源限制。原始复场及固定K、各级入瞳能量见raw/P1_RS_q*.npz和boundary_pointwise_rs.csv。
稀疏成对点标签：{'PHYSICAL_TAIL_SUPPORTED': 0, 'PERIODIC_OR_SAMPLING_ARTIFACT_SUPPORTED': 0, 'MIXED': 8, 'INCONCLUSIVE': 34}。本轮没有把点位乘面积来估计整条带edge_fraction。
周期ASM对照pads=[2, 4]，用GPU FFT谱+分块精确核+选点逆DFT，未保存或生成整域传播强度。相同物理点复场、强度、相位差及原ROI控制核对见boundary_asm_rs_comparison.csv与raw元数据。
原冻结pad2/pad4边界份额0.001376161206/0.000616555406属于四边16um条带/有限域总量，不是ROI边缘或环绕误差直接测量。原0.001门与主盘外峰比差0.1门均未改变。
若4→8尚不满足诊断收敛，周期与输入采样贡献不能可靠拆开；即使个别点稳定，也不代表全条带或25+加密波长通过。

## 3. P2：546.1nm固定主盘中心诊断

{'status': 'COMPLETED_LOCAL_DIAGNOSTIC', 'RS_q1_q4_local_candidate_ratio_difference': 0.0011639483440459841, 'output_area_done': True, 'full_ROI_RS_certified': False, 'source_q8_done': False, 'old_G3': 'FAIL'}
原完整旧图三口径与新局部RS在peak_mask_sensitivity_rs.csv分列；物理共同中心、主/旁候选坐标及掩模半径先于计算冻结。新输入像元高度不插值、不量化；旧dx0.5图属于历史重新采样高度，不能当本轮同高度独立物理真值。
完整分子/分母与候选集定义见peak_ratio_definitions.json。新RS局部比不等于全ROI盘外最大值；输出像元面积2x2并未取得输出求积收敛证书，禁止以共同掩模差变小给旧G3改判。

## 4. P3：425nm证据保留

**评价器不稳定有证据，单圈物理模态尚未完全认证**。独立从原NPZ重算Hessian与偏移、同一49点RS误差，实际5nm pad4间隔核查通过，详见425_evaluator_evidence_check.md/json。没有新全带证据，旧G2仍FAIL。

## 5. 数值模型、自测与资源

高度原文件SHA=8166b58c358b3be2862cd9401f17b6bdd6ad5dcc575e5278aaa135f28b5ba19f，固定原1um源像元分片常值；孔径mask亦在原像元内保持二值常量，不在亚像元重裁圆孔。球面入射振幅/曲率与RS法向因子在子点实际坐标计算，子面积1/q² um²，全部求积共用原入瞳K。
RS1复核包括小方孔轴上解析幅值、对称瞳孔复场对称、CPU/GPU及不同分块、独立NumPy子像元循环；选点ASM另与完整小网格IFFT核对。实现自测5/5 PASS。
环境：D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe；torch 2.5.1+cu121，CUDA 12.1，GPU NVIDIA GeForce RTX 4060 Laptop GPU，NumPy 2.2.6，SciPy 1.15.3。未安装依赖。HEAD=b9bf90c94bda664502d309be147949262fa71309，dirty见git_dirty_before.txt。
预检见resource_preflight.json；执行墙钟9.48s，CPU本进程峰值工作集0.837GiB，记录的最大GPU分配3.008GiB。RS按8192源像元×4输出点分块；未跑pad5/pad8或全波段传播。
历史7360文件保护核查PASS；使用的历史二进制及报告/协议输入SHA见input_hashes.json，新增源码见source_hashes.json，全部输出SHA见artifact_manifest.json。全过程未覆盖/删除历史产物，未安装、提交或清理Git。

## 6. 下一项最低资源实验与停止位置

仅在420nm同一8个预注册边界点追加16x16源像元内RS中点求积，与8x8比较，或对同一分片常值源做有误差界的像元相位积分；先排除尚未收敛的输入求积，不扩谱、不重新设计。
当前只结案于机制归因和下一轮决策。即使局部证据支持周期污染或掩模敏感性，也须未来独立新run取得受控全边界证据、全部25+加密波长及完整硬门验收后，才可申请重新冻结；本轮不自动恢复G4–G8。

## 可复现命令

```powershell
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B experiments/n02_1c_r2/r2_run.py --run-id n02_1cr2_replay_unique
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B experiments/n02_1c_r2/r2_verify.py --run-id n02_1cr2_20261020_02
```
唯一run目录拒绝覆盖。配置configs/n02_1c_r2/protocol_v1.json；点位与协议在计算前落盘，见preregistration.json。
