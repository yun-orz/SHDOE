# N02-1C-R 审核版 v2（本轮权威汇总）

本文件保留v1全部原始结果，增加离线核查澄清；没有覆盖v1、旧N02或Gate。最终P0B仍 **INCONCLUSIVE**；A支持 **EVALUATOR_INSTABILITY**，B仍 **INCONCLUSIVE**。G2/G3 FAIL不变。

## 必须优先阅读的更正与补充

- **实际资源范围**：新增大网格ASM为0。预检RAM仅1.863GiB，低于2GiB下限；pad5预算还超过显存余量。只复用旧pad2/pad4与dx0.5数据；没有10240um新域计算。新增计算为13个非周期Fresnel积分及4组局部RS，CPU工作集峰值0.994GiB。
- **谱间隔修正**：旧pad4蓝端只存在420/425/430nm。v1的三个点之间角差被误套1nm门，v2在`blue_domains_trajectory_v2.csv`按实际5nm间隔缩放。完整pad2与开放Fresnel的420–430nm/1nm结果保持；未据任何诊断表更改旧G2。
- **初值范围澄清**：A的六种估计器主审计使用8方向初值；B的插值比较使用4方向初值。`gpu_peak_allocated_bytes=0`只表示无新GPU ASM调用，不能解释为CUDA环境不占显存。
- **非边缘失败的机制证据**：546.1nm细采样原峰比差0.298764，在共同物理主盘中心下为0.002715；再统一像元面积采样为0.006625。660nm pad4原差0.103491，在共同中心下为0.009859。说明主盘中心及离散排除掩模有强敏感性；这些是并行诊断，**不放宽原0.1门**，也不证明原像元内部高度求积已收敛。
- **425nm开放RS峰形**：0.25um子网格的诊断峰坐标约(13.954184,-21.703556)um。核心49点中pad2/RS L1=0.002530524，pad4/RS L1=0.000007572。该局部证据支持微小数值扰动触发冻结拟合失稳；没有认证整ROI或全边界能量。

图：`diagnostics/425_open_reference_comparison_v2.png`；证据：`review_corrections_v2.json`、`P0B_gate_decision_v2.json`、`ratio_sensitivity_decomposition.csv`、`RS_core_error_summary.csv`。

## 下一项最小实验（替代v1的下一项建议）

只在420nm，对冻结1um B2高度的若干边界条带成对位置做2x2/4x4像元内RS求积，同点比较既有pad2/pad4：先区分真实衍射尾与周期/输入采样纹理。不改0.001门、不启动G4–G8。

## v1证据汇总（涉及计算域/初值/谱间隔的表述以上述v2澄清为准）

# N02-1C-R 执行总结

## 1. 实际范围与决策

只执行A1–A3、B1–B3和C。P0B判定：**INCONCLUSIVE**；A=EVALUATOR_INSTABILITY，B=INCONCLUSIVE，C独立口径复核完成。没有启动G4/G5/G6/G7/G8，没有新DOE、软环带、训练或场景重建。
旧G0/G1 PASS、G2 FAIL、G3-Numerics FAIL、工艺SIMULATED_ASSUMED完成标签、G4–G8 NOT_TESTED全部保持，未回写任何旧文件。旧571 NPZ重新回读，900个冻结产物逐一SHA核对；旧PASS不是仅从gates.json固定标签推断。

## 2. A：425nm与蓝端

独立复现425nm冻结Hessian=[-0.028904506108991465, -0.005247731840996713]、驻点偏移=[1.4790130308188043, 0.12147172081873285]pixel、条件数=5.508000。负定而偏移超门，clip样本0；不是Hessian非负，也不能自动说双峰篡位。
420–430nm/1nm的原始PSF均一个半峰连通域；冻结1nm角差多个区间仍超0.4–1.8°，见blue_1nm_trajectory_comparison.csv。6定位器、8类合成峰测试、pad4/开放Fresnel轨迹及425nm开放RS子网格均已保存。
局部非二次性、弱曲率和数值域改变支持EVALUATOR_INSTABILITY。估计器离散度只作角度误差代理，不能把微分波动直接等同真实旋转回折。反证：局部11点不证明全带唯一物理模态，限制见blue_branch_identity.md。

## 3. B：边界与非边缘失败

旧edge_fraction为整个传播域四边16um条带/有限域总能量，**不是ROI边缘，也不是FFT环绕误差直接测量**。条带求和区域与面积定义见boundary_metric_definition.md。
原必需比较13条，11 FAIL/2 PASS；除边界门，还有660nm pad4峰比差0.10349和546.1nm dx0.5差0.29876超0.1。原checks.edge取候选/旧基线最大值，本轮逐列分开，未改变门槛。
新增ASM 0次，均在420、421–429、546.1、660nm允许集合及资源预算内；4096um/pad2、8192um/pad4、10240um/pad5始终比较同512um ROI。未运行预算不允许的更大网格。
非周期Fresnel-CZT与局部RS为非同源边界参照，精度测试见implementation_self_tests.json；局部RS对各模型误差见RS_core_error_summary.csv。物理长尾与数值周期/采样效应未完全分离，仍INCONCLUSIVE；不能说加padding已经解决全部G3问题。

## 4. C：光能、像元和Gram

25标准通道独立回算：ROI/入瞳73.613761–88.579405%，主盘/入瞳最低8.355412%。所有ROI归一化副本仅用于形态，不冒充绝对效率。
理想1/2/4/8um像元100次面积积分保持能量，峰半径、位置及谱相关性见pixel_integration_effect.csv。未使用真实MTF/噪声/吸收反射数据。
L2列归一强度Gram独立重建，条件数=224053.557938632，熵有效秩=7.085220929，代数秩=25；SVD独立复核。光子权重后条件数=215927.427035397、有效秩=7.015432641，权重仅是假设纯谱收集数的字典诊断，不是HSI成绩或双孔径必败证据。
原17组工艺假设扰动有6组未保持25/25；原PASS只能解读为实验完成，不等于工艺鲁棒性合格。

## 5. 可复现性、版本与资源

仓库HEAD=b9bf90c94bda664502d309be147949262fa71309，起始dirty清单见git_status_before.txt；代码仅新增experiments/n02_1c_r、configs/n02_1c_r，结果和报告使用唯一新run-id。
Python=D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe；torch=2.5.1+cu121，CUDA=12.1，GPU=NVIDIA GeForce RTX 4060 Laptop GPU，NumPy=2.2.6，SciPy=1.15.3，随机种子20261020。未安装依赖。
5项独立实现自测全部PASS。历史7261文件保护PASS；完整输入SHA见input_hashes.json，代码版本见source_hashes.json，产物SHA见artifact_manifest.json；旧Gate SHA=a9855429b0d94ac842496b32d0c18319f873ea9882415c5e8463a4dc6fd8d0a4。
CPU本进程峰值工作集=0.994GiB，GPU新ASM分配峰值=0.000GiB，本轮墙钟=139.23s。资源预检、调用清单及逐次运行时间见resource_preflight.json、execution_ledger.jsonl、resource_usage.json。
完整命令（运行前处于仓库根；新run-id不可复用）：
```powershell
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B experiments/n02_1c_r/p0b_run.py --run-id n02_1cr_replay_unique
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B experiments/n02_1c_r/p0b_verify.py --run-id n02_1cr_20261020_01
```
P0B_diagnostic_protocol.json在新传播前冻结，旧新口径全部并列old_new_parallel_comparison.csv；约束/插值/开放参考均未替换原评价器。坐标x右y上、长度um、波长nm、距离mm、强度um^-2/单位入瞳。

## 6. 未测试项及下一项最小实验

未认证原1um像元内部传播积分收敛，未获得全开放RS边界条带面积积分，未分离旧dx0.5重新量化与探测盘取样的全部影响；未做真实材料/工艺/MTF/噪声标定。没有新门禁PASS。
只在546.1nm，将冻结1um B2高度解释为分片常值，对同一局部主/旁峰及主盘边缘坐标进行2x2/4x4像元内RS中点求积；固定同一主盘中心并并列冻结输出，以区分输入求积误差与主盘掩模敏感性。不得由此自动启动G4–G8。
该实验针对目前最大的非边缘反例，能以单波长固定高度区分“输入求积/量化边缘”与“主盘定义/采样”两种假设。未经后续明确授权，不恢复G4–G8。
