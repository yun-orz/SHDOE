# N02 复核摘要

标准25点B2形态/链接PASS（244.849226°），但425nm蓝端定位FAIL、G3边缘门FAIL。L1未通过，L2/L3未测试；禁止以标准25/25替代全门禁。

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
