# EXP2交付复核与关键解释



EXP2 exploratory; N02 G2/G3_Numerics=FAIL; N03 G0=FAIL. No certified physical DOE performance.



最终权威结果目录为`E:\SH\reports\N03\EXP2_20261020_03`。首次失败及较早离散Gaussian版本的目录均保留，只按本目录解读结论。

原diagnostic_25bands.png来自通用9带模板，副标题含9带/NNLS通用文字；25带确实只有矩阵预诊断，正确专用图为figures/diagnostic_25bands_verified.png。本次未改写原图，避免掩盖绘图模板问题。

补充figures/mismatch_sam_log.png呈现所有五个失配族的SAM曲线；原mismatch_nrmse_log.png主要呈现四类机制，y方向的全部原始指标仍完整保留。

独立几何未覆盖权重计算outside的最大相对守恒误差=3.33067e-16；B2 detector子视场损失范围=0.000325989485–0.00182199567（相对原归一ROI）。这不是原大ROI未收集的全域光损失。

Q协议（含失配Q40）最大实际SNR误差=7.10543e-15dB；P三模型同谱/同P_in的期望总电子相对差最大=6.31034e-16。

最坏M1谱例：shift_y_-0.5、onehot_630、seed=0，NRMSE=0.121315。

Q40下M1/同模型M0误差比的中位数=196.977，最大=8915.14；倍数依赖极低的M0噪声基准，应与绝对误差一并看。

协议P中B2阵列实际SNR可为负，但谱误差仍可低于秩亏控制：全ROI读噪总范数包含很多与低维编码子空间正交的分量。该结果不意味着低SNR任意场景可恢复，也不意味着真实相机的相关噪声或失配可忽略。

P低预算/高读噪时，B2的最坏谱误差明显增大；throughput-aware会进一步降低有效电子量。9带在理想噪声下有增益，不等于具备硬件认证。25带条件数约1439.91、最大邻列余弦约0.96273，明显比9带病态，仅支持谨慎的后续探索。

结论仍为CONDITIONAL GO：先针对位置/响应标定及物理数值收敛补证据，不自动开启25带恢复、场景重建或新DOE优化。
