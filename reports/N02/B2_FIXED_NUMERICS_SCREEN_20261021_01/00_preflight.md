# B运行前审计

EXP2B EXPLORATORY, archived PSFs; N03 G0 FAIL; N02 G2/G3_Numerics FAIL.

原boundary_sample_plan哈希与preregistration一致，原R2产物哈希逐项通过；固定8点为B006, B007, B008, B009, B010, B011, B012, B013。它们是像面边界输出位置，不是源面采样点；仅得到8个复场/强度值，不构造二维PSF或ROI边缘能量。

只读提取原r2_solver.py:6的rs函数和r2_common.py:102的source_pixels函数，不改函数体，不运行旧入口。同K、同几何、同8192源像元/4输出点块，仅q从8变16；高度/孔径在原像元内分片常值。

历史q8=1.154s，估计成对筛查43.1s，估计GPU峰值1.251GiB，当前空闲6.476GiB，allowed=True。阈值已冻结：同通量强度向量L1≤1%，并保留R2每点复场≤1%/强度≤2%诊断口径；不替代原edge<0.001或425nm拟合偏移≤1pixel门。
