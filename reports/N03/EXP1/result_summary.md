# EXP1 探索性结果

EXPLORATORY ONLY — archived B2 PSF numerical-convergence certification is incomplete; results do not establish physical DOE performance.

EXP1-A/B/C已完成，EXP1-ENTRY PASS；原N03-G0 FAIL、N02 G2/G3_Numerics FAIL保持不变。未做25波段、正则化、物理像元重采样或失配实验。

## 契约与实现

9波长固定为420/450/480/510/540/570/600/630/660nm；对应31点相机响应索引2/5/8/11/14/17/20/23/26（从0开始），R/G/B不交换。共同除以原31点绿色曲线之和，不乘Delta-lambda。s是每带已积分能量，所有真值总和1。
采用shape_only、1um native-grid diagnostic、512×512固定ROI。B0统一delta位于(+0.5,+0.5)um；B1复制540nm；B2保留归档峰位。半像元轴心不变，无图像卷积，无reflect边界、gamma、裁剪、逐通道曝光或重新居中。
throughput_aware仅讨论可行性：可按raw_roi乘1um²保留捕获率，但因该通量尚未完成数值认证本轮不运行；shape_only舍弃73.61%–88.58%类ROI捕获差异，不能解释真实相机/硬件优势。
A为786432×9 float64，行顺序R全部像元、G全部像元、B全部像元，像元按行优先。独立渲染逐波长逐通道相加强度；建矩阵采用广播与轴变换。
求解使用SVD正交压缩：A=UB，||As-y||²=||Bs-Uᵀy||²+||(I-UUᵀ)y||²，第二项不依赖s。仅舍弃数值零奇异方向，保留全部非零子空间；不是列归一化。NNLS全部三组共用相同标量缩放，且无谱平滑/稀疏先验。原矩阵、压缩目标与KKT有实际测试。
噪声只采用common_absolute_noise。预先定义B2均匀谱为参考，而非分别给三模型或各测试谱调曝光；所有模型/谱共享sigma，同谱/种子共享完整高斯噪声场。40/30dB是参考名义SNR，实际SNR逐例见metrics.csv。此选择会让delta的实际SNR远高于扩散PSF，正是固定每像元读噪声预算下的控制结果，不等同真实Poisson相机。
## 数值诊断

|模型|秩|sigma_min/max|条件数|最大非对角余弦|
|---|---:|---:|---:|---:|
|B0_RGB_delta|3|1.52603e-34|rank_deficient|0.998663|
|B1_fixed_PSF|3|2.37295e-17|rank_deficient|0.998663|
|B2_spiral_PSF|9|0.174263|5.738453872089251|0.704052|

秩阈值eps×max(A.shape)×sigma_max；rank_deficient明确表示非唯一，非零子空间条件数另存JSON。列范数保留原响应，归一列余弦仅用于诊断。

## 三组恢复数据

|条件|模型|NRMSE均值±种子SD|SAM度均值±种子SD|传感器相对残差|
|---|---|---:|---:|---:|
|noiseless|B0_RGB_delta|0.466896 ± 0|23.8018 ± 0|2.08385e-16|
|noiseless|B1_fixed_PSF|0.466896 ± 0|23.8018 ± 0|2.14445e-16|
|noiseless|B2_spiral_PSF|2.93618e-16 ± 0|1.14511e-07 ± 0|3.01571e-16|
|common_absolute_40dB|B0_RGB_delta|0.466897 ± 4.41e-08|23.8018 ± 3.98e-07|6.23474e-05|
|common_absolute_40dB|B1_fixed_PSF|0.466952 ± 1.41e-05|23.8044 ± 0.000709|0.00499857|
|common_absolute_40dB|B2_spiral_PSF|2.5396e-05 ± 1.1e-06|0.00132839 ± 5.49e-05|0.00686602|
|common_absolute_30dB|B0_RGB_delta|0.466898 ± 1.4e-07|23.8018 ± 1.25e-06|0.00019716|
|common_absolute_30dB|B1_fixed_PSF|0.467071 ± 4.47e-05|23.8101 ± 0.00224|0.0158049|
|common_absolute_30dB|B2_spiral_PSF|8.03094e-05 ± 3.49e-06|0.00420076 ± 0.000174|0.0217061|

NRMSE=||ŝ-s||₂/||s||₂；SAM=acos(sᵀŝ/(||s||₂||ŝ||₂))的角度值，预测全零则null而非伪造0度。幅值偏差同时保存sum(ŝ)-sum(s)、相对总能量偏差和L2幅值偏差。主峰误差对真值并列最高峰取最近者；双峰另存两最高恢复带是否匹配真实支撑，不能只靠主峰判断双峰分辨。
每条件先对全部18谱取均值，再对3个种子求均值/样本SD（不是把54个样本混为3次重复）；无噪声只有1次。所有378次逐例结果和真值/解完整保存。

## 六项复盘

1. B2数值秩9，控制组秩3；B2条件数5.738453872089251。是否低误差应同时查看无噪声和噪声表，不能把满秩当作任意噪声下可稳定恢复。
   - onehot：参考30dB时B2平均NRMSE=3.74135e-05，平均SAM=0.00164479度。
   - double：参考30dB时B2平均NRMSE=5.19499e-05，平均SAM=0.00260875度。
   - broad：参考30dB时B2平均NRMSE=0.000174301，平均SAM=0.00991319度。
   - random：参考30dB时B2平均NRMSE=0.000184149，平均SAM=0.0101831度。
2. 预定义全谱中B2最差噪声个例是random_2，seed=20261021，NRMSE=0.000334625，已单独画图；近双峰/远双峰和单带全覆盖，成功失败项均保留。
3. 本轮仅报告统一绝对噪声口径，未做每模型自身归一的mathematical_SNR。实际信号范数、sigma、实现噪声范数和实际SNR逐例公开；不能把参考SNR标签当作各模型的实际SNR。
4. 对照仅支持整体波长依赖PSF的编码差异；没有旋转消融，不能把差异唯一归因于螺旋旋转。
5. 原生1um网格、shape_only、精确已知位置与精确同模型合成/反演均为理想化假设；实际像元积分、通量、材料标定、PSF失配和原数值收敛问题足以改变结论。NNLS成功仅指优化成功，不表示秩亏解等于真值。
6. 建议可单独审核25原生波段与模型失配/面积积分的EXP2探索，并继续独立的物理数值认证。物理认证与本次算法探索分开标注；本轮不执行EXP2或新的求积。

## 非唯一性证据

nonuniqueness_example.json保存两条总能量相同、非负且不同的光谱；谱距离0.0775027，对应各组相对观测差为{'B0_RGB_delta': 4.9786688153648065e-17, 'B1_fixed_PSF': 5.69344064741446e-17, 'B2_spiral_PSF': 0.09728369615949474}。控制组即使残差极小仍可恢复错误光谱。

## 测试、产物与运行

58项PASS、0项FAIL；数值证据见validation_results.json。测试涵盖全部三模型×9列的独立渲染、多谱前向、伴随、线性、零输入、物理RGB toy、解析NNLS、秩亏、控制核相同和压缩残差/KKT。
新增代码仅在integration/single_spiral_to_hsi/n03_exp1及tests/test_n03_exp1.py；新增结果仅在本EXP1目录。输入SHA、Git HEAD/dirty、依赖、光谱生成规则与种子均在run_config.json。旧输入及用户已修改README的前后SHA保持不变；未Git提交、回滚、删除或修改框架。
图表：figures/archived_psfs.png、matrix_svd_norms_response.png、column_cosine.png、noise_summary.png、spectrum_onehot_540.png、spectrum_near_equal.png、spectrum_broad_510.png、spectrum_random_0.png、worst_spiral_case.png。全部图带探索声明。
逐例数据metrics.csv/spectra_results.json；汇总summary_metrics.json；矩阵诊断matrix_diagnostics.json；真实事件日志logs/events.jsonl；噪声标定noise_calibration.json。

## P0/P1/P2与停止位置

- P0：没有工程ENTRY失败；原G0及N02数值认证失败事实仍保留，物理性能未认证。
- P1：精确模型下的9带优势不能推广为真实相机、完整HSI、双孔径或旋转单机制结论；后续需失配/采样和物理可信性证据。
- P2：18条合成谱、每噪声3种子是首轮规模，尚无25带、谱平滑、Poisson、实测光谱或未知位置实验。
完成EXP1后停止，请交ChatGPT审核。
