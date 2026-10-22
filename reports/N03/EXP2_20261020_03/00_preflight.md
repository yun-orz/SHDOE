# EXP2-0 输入及契约

EXP2 exploratory; N02 G2/G3_Numerics=FAIL; N03 G0=FAIL. No certified physical DOE performance.

从传感器JSON的12.34mm/4504像元得到pitch=2.739786856128um，运行时M=floor(512/pitch)=186；矩阵应为103788×9。detector边界[-254.800177619893,254.800177619893]um，fine边界[-256,256]um，光轴均为(0,0)。EXP1已读run_config/matrix_diagnostics/summary_metrics/run_record及源代码，全部归档产物哈希一致；RGB严格沿用索引[2,5,8,11,14,17,20,23,26]，不交换R/B。EXP1记录378次求解、耗时6.217s；本轮将复核S0条件数。原采样为1um ROI质量；本轮粗像元作面积积分。crop_fraction为有限传播域参考ROI份额，raw_energy在各波长约1；它不是材料绝对透射率或实测QE。协议P的全局模拟电子缩放K=9.57266410934，原始完整31点表确定，所有模型不变。模拟预算及读噪声明为情景假设。原N03 G0 FAIL、N02 G2/G3 FAIL保留；工程检查不能替代物理数值认证。

Git/dirty、实际路径、源代码/输入SHA与版本见run_config.json、input_manifest.json。
