# 546.1nm局部峰比与掩模机制

P2执行完成；物理全ROI验收仍INCONCLUSIVE，旧G3 FAIL不变。
完整定义见peak_ratio_definitions.json。原分子为ROI最大像素强度；原分母为离各自3x3拟合中心严格大于1.22lambda*z/D的所有ROI像素的最大值，不要求分母点是独立局部旁峰。distinct_side_ratio是另一候选定义。
三列证据并排：frozen_original是各自旧中心与原生网格；parallel_diagnostic是共同物理中心、旧细图2x2面积对齐；physical_reference是同一原高度分片常值的1/2/4输入求积与固定少量候选输出。
本轮RS候选集合1x1至4x4的局部峰比绝对变化=0.00116394834405；坐标、分子/分母强度均在peak_mask_sensitivity_rs.csv中，不把旧0.298764等数值冒充本轮物理差。
新RS始终固定共同中心，不在每级重新拟合取得更好结果。候选是否从盘内变盘外取决于几何与原网格，不是新生物理旁瓣，见peak_candidate_geometry.csv。
统一输出像元面积求积状态=True；仅2x2中点近似，另列中心判外与物理半径裁切后的盘外面积均值。两者定义不同，不混用；输出求积收敛、完整ROI最大值和8x8源输入均NOT_TESTED。
因此本轮可分析掩模/采样敏感性及固定局部主/旁峰的输入求积影响，不能给真实全局峰比或冻结0.1门授予通过。
