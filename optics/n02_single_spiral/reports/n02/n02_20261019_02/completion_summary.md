# 本轮完成状态

P0计算、失败诊断、工艺假设量化与独立归档完成；科研G2/G3 FAIL。P1/P2按数值停止条件未执行，非已验证失败。

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


入口：experiments/n02/run.py；复核：experiments/n02/verify.py；总报告：N02_final_decision.md。
