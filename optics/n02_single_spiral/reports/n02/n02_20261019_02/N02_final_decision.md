# N02 本轮执行与科研决策

## 1. 本轮实际执行范围

完成N02-0、N02-1A、N02-1B（25标准通道、546.1nm参考、420–500nm/5nm及421–429nm局部1nm）、N02-1C（关键数值收敛、独立实现、17组×25通道工艺/材料假设扰动、像元积分）。
    原首轮n02_20261019_01在量化测试浮点边界判断失败后停止；修正测试的整数级别核对后本轮12/12通过。首次本轮因validation模块尚未落盘、首次续跑因历史run模块名冲突、计算完成后因reporting模块尚未落盘中断；均保留原traceback与续跑记录，随后以绝对文件导入隔离并用finalize.py独立归档，未覆盖结果。没有重跑已完成标准传播。
P0实验/诊断及归档已完成，科学失败仍保留。依据任务书第14节停止条件，G3边缘门未满足后未开展P1结构扫描、低维优化、G7双孔径和G8重建。

| Gate | 状态 | 实际范围 |
|---|---|---|
| G0 | PASS | SIMULATED；12/12物理测试及冻结协议/历史路径审计 |
| G1 | PASS | SIMULATED；B2固定高度25标准通道物理/形态/链接与旋转成立 |
| G2 | FAIL | SIMULATED；425nm冻结3x3拟合不稳定；1nm局部若干角符号误差代理/缩放角差门不通过；不能仅报标准25点 |
| G3_Numerics | FAIL | SIMULATED；多个波长全域16um边缘能量未达冻结0.001门 |
| G3_Fabrication | PASS | SIMULATED_ASSUMED；完成有界假设扰动定量，实测工艺NOT_TESTED |
| G4 | INCONCLUSIVE | NOT_TESTED；G3关键数值门失败，依据任务书停止条件停止结构扫描/优化/双孔径与重建 |
| G5 | INCONCLUSIVE | NOT_TESTED；G3关键数值门失败，依据任务书停止条件停止结构扫描/优化/双孔径与重建 |
| G6 | INCONCLUSIVE | NOT_TESTED；G3关键数值门失败，依据任务书停止条件停止结构扫描/优化/双孔径与重建 |
| G7 | INCONCLUSIVE | NOT_TESTED；G3关键数值门失败，依据任务书停止条件停止结构扫描/优化/双孔径与重建 |
| G8 | INCONCLUSIVE | NOT_TESTED；G3关键数值门失败，依据任务书停止条件停止结构扫描/优化/双孔径与重建 |
| GF | PASS | SIMULATED；完成本轮P0证据归档与独立回读；科研L1/L2/L3不因此通过 |


## 2. 最重要的数值结果

全部为SIMULATED；材料模型为ASSUMED Cauchy n(λ_um)=1.5292+0.00800/λ_um²，非实测IP-Dip2曲线。设计546.1nm；n=1.556025364630；p=0.982149439107um。
R500um，f20mm，物距180mm，固定探测面22.495mm。2048²输入、dx1um、padding2输出4096²、complex128精确ASM；固定512um ROI。只生成一张实体高度，10级floor量化、孔径外振幅为零。各波长高度SHA一致。
每波长原始强度、归一副本和完整面积能量见`B2/cases/*nm.npz`；逐波长指标见`B2/standard_metrics.csv`与`gate2_psf_metrics.csv`；全部候选/可行边/未匹配记录见`B2/*_all_peaks.csv`与`B2/*_all_edges.csv`。
最高相邻未去均值PSF余弦0.962458042，Gram有效秩7.085221、Gram条件数224053.557939；这是强度字典诊断，不等于未知场景HSI可辨识。
主峰半径25.32606–39.77041um，CV=0.132734，不是整图刚性旋转。
标准相邻角差范围6.111486–16.323359°；误差代理和逐段门保留原数值，不四舍五入凑PASS。

| 项目 | 原W/C/F2（NON-FAIR REFERENCE） | N02硬环带B2 | 软环带 | 优化 | 证据 |
|---|---|---|---|---|---|
| 最大高度um | W 1.195884 / C 55.505381 / F2约10.668（原文件另核） | 0.883934495 | NOT_TESTED | NOT_TESTED | B2/height_metadata.json；历史N01-2A报告 |
| 波段/材料/孔径 | 400–700nm / 熔融石英 / R1000um | 420–660nm / ASSUMED IP-Dip2 Cauchy / R500um | NOT_TESTED | NOT_TESTED | config_resolved.json |
| 单峰通过数 | W14/31；C31/31；F2 12/13，蓝端失败 | 标准25/25；蓝端16/17 | NOT_TESTED | NOT_TESTED | B2/*_metrics.csv |
| 累计旋转 | C -82.2099°；W/F2全带身份不成立 | 标准+244.849226°；加密门失败，不宣称全连续带成立 | NOT_TESTED | NOT_TESTED | B2/standard_links.csv |
| 标准唯一链接 | 历史波长集合不同 | 24/24；蓝端唯一16/16但可信14/16 | NOT_TESTED | NOT_TESTED | B2/*_all_edges.csv |
| 最差/平均主盘外峰比 | 历史见原CSV | 2.634557 / 3.107301 | NOT_TESTED | NOT_TESTED | B2/standard_metrics.csv |
| 主瓣绝对效率（单位入瞳） | 不同几何不作公平对比 | 最低8.355%；平均18.926% | NOT_TESTED | NOT_TESTED | 同上 |
| ROI收集效率 | 历史512um窗口未过99% | 73.614–88.579% | NOT_TESTED | NOT_TESTED | 同上 |
| 数值收敛 | C条件通过、W端点失败 | G3-Numerics FAIL（边缘能量）；核心形态/位置误差较小 | NOT_TESTED | NOT_TESTED | gate3_convergence.csv |
| 加工容差 | 历史非同条件 | 17组有界假设扰动已量化，实测NOT_TESTED | NOT_TESTED | NOT_TESTED | gate3_fabrication.csv |
| 谱诊断/双孔径 | NON-FAIR REFERENCE | Gram条件数2.24e+05；有效秩7.085；双孔径NOT_TESTED | NOT_TESTED | NOT_TESTED | B2/standard_gram.npz |
| Gate | 只读历史 | G0/G1 PASS；G2/G3-Numerics FAIL；L1未通过 | NOT_TESTED | NOT_TESTED | gates.json |


## 3. 最严重的三个风险/反例

1. **425nm冻结定位失稳**：原1um/pad2的3×3对数二次拟合诊断为`OFFSET_EXCEEDS_ONE_PIXEL`，偏移像素=[1.4790130308188043, 0.12147172081873285]，原始强度仍单半峰域且峰比约2.696149。这是定位/采样风险，不能冒称已观察双峰篡位。5nm蓝端16/17通过；自适应局部24/25通过且仅18/24可信链接。证据`425nm_fit_failure.png`、`425nm_fit_diagnostics.csv`、`blue_peak_diagnostics.png`。
2. **有限域边缘门未满足**：420nm标准边缘份额=0.001376161，660nm=0.001164485，均与冻结0.001比较；padding4/细采样的失败逐项见`gate3_convergence.csv`。pad4相对pad2的ROI形态L1最大0.031685，峰位差最大0.480503um；dx0.5最大L1=0.025765。独立CPU精确ASM的L1最大2.09e-12，证明实现一致，不能消除两者共享的有限域风险。图`gate3_convergence_differences.png`。
3. **收集/主瓣效率与相关性风险**：420nm主盘/入瞳仅8.3554%，512um ROI/入瞳73.6138%；标准ROI之外能量最高26.3862%。所有25标准点ROI99 FAIL。相邻通道余弦最高0.962458，未验证噪声下双谱/连续谱估计。假设高度缩放/圆角/横向采样造成的具体失效点均保留于17组文件，不能用ROI归一掩盖。图`B2/metrics_trajectory_gram.png`。

## 4. 可复现性

仓库HEAD `b9bf90c94bda664502d309be147949262fa71309`，起始dirty全文见git_status_before.txt；本轮新增文件清单和SHA见source_hashes_final.json。历史6326文件保护核查PASS（size/mtime；文本另有SHA），未覆盖任何N00/N01结果，未提交/重置/清理Git。
Python `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe`，torch 2.5.1+cu121，CUDA 12.1，GPU NVIDIA GeForce RTX 4060 Laptop GPU，NumPy 2.2.6，SciPy 1.15.3；未安装新依赖。种子20261019。
物理测试12/12 PASS；独立归档回读571份NPZ PASS；最大Parseval误差5.96e-07（包含complex64对照）。GPU已记录的最大分配显存3.313GiB，逐次运行时间/显存见propagation_ledger.jsonl，累计已记录传播时间278.80s（不含全部绘图、压缩、CPU审计和中断间隔，不能冒充总墙钟时长）。
复现命令（新run-id，禁止覆盖）：
```powershell
& 'D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe' -B experiments/n02/run.py --run-id n02_replay_unique
& 'D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe' -B experiments/n02/verify.py --run-id n02_20261019_02
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
