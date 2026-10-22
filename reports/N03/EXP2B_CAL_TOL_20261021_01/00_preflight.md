# A运行前审计

EXP2B EXPLORATORY, archived PSFs; N03 G0 FAIL; N02 G2/G3_Numerics FAIL.

EXP2最终47项产物已按final_manifest只读核验；读取主体报告、补充报告、配置、9/25带诊断、metrics、input_manifest及源码快照。接口路径和具体行号见run_config.interfaces；输入SHA见input_manifest。

完全复用EXP2正式连续面积积分detector_perturb，而非旧离散shift；固定A_nominal、18谱及3个原seed。17个唯一位置×18谱×4观测=1224次NNLS，预计CPU约10–30秒。原工作区dirty如实记录，无清理。

shape_only会在detector裁切后归一，舍弃其通量差异；Q40只匹配全ROI实际SNR，不混用P_in。1%主阈值及0.5%/2%参考先于求解冻结，属于本实验操作性判据而非加工标准。
