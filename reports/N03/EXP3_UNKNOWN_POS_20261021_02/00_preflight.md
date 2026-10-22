# G3-0 只读预检 PASS

EXPLORATORY ONLY / optical G0 FAIL — archived B2 optical PSF is not full-domain numerically certified; image-plane shift-invariance is an approximation

EXP2 final_manifest及EXP2B artifact_manifest逐项核验通过。全部既有reports、optics、integration源码、传感器和README已冻结SHA-256，见input_manifest。HEAD及原dirty状态见run_config。原N03 G0与N02 G2/G3_Numerics保持FAIL。

接口真实文件和行号见run_config.interfaces。归档512方格为1 μm分片常数像元，中心index−255.5，边界−256至256 μm；光轴在四格交点，186偶数detector的光轴也是四格交点，不假设有唯一中心像素。pitch=2.7397868561278864 μm；正dx向列增加，正dy向行增加。对源边界加(dx,dy)*pitch，零延拓，无周期绕回。固定ROI、物理RGB通道优先展平。s是九个离散带积分能量。

连续双轴位移使用EXP2B所调用的overlap_matrix/rebin原函数。逐带shape_only归一严格沿用EXP2B，并记录每个位置的归一前capture；该定义舍弃位置引起的裁切通量，不添加RGB整体增益自由度。不是光学传播重认证。

算法与阈值先于实验冻结：3×3粗网格，最低残差两个起点各55次Powell，最多119候选。单例只有y和固定模型输入。pilot48观测，full504观测；预计full超过3600秒则PARTIAL停止。
