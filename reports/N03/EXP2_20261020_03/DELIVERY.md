# EXP2 最终交付入口

**EXP2 exploratory；N03 G0=FAIL，N02 G2/G3_Numerics=FAIL，均保留不变。**

EXP2已完成。最终权威结果为本目录；`EXP2_20261020_01`保留pilot求解器失败证据，`EXP2_20261020_02`保留早期离散扰动版本，均未删除或覆盖。最终数值与结论仅引用本目录。源码快照位于`logs/source_snapshot/`，逐项SHA见`source_manifest.json`；完成时的全体产物校验见`final_manifest.json`。

## 先读哪些文件

1. [主体报告](result_summary.md)：实验契约、完整诊断/噪声/失配表、限制及后续建议。
2. [交付复核与解释补充](interpretation_addendum.md)：独立守恒核验、P/Q公平性、最坏例和修正后的25带专用图。
3. [交付检查](delivery_qa.json)、[基础测试](tests.json)、[运行检查](postrun_checks.json)：真实数值与通过情况。
4. [实际命令与复跑](run_commands.md)、[运行记录](logs/run_record.json)、[事件日志](logs/events.jsonl)。

## 关键结果

- 从传感器JSON精确计算pitch为2.7397868561278864μm；186×186个完整像元，RGB矩阵103788×9。采用几何面积积分，不是图像插值。
- B2在1μm原网格与面积积分后均为秩9；条件数从5.73845变为5.77772；B0/B1仍为秩3。throughput-aware的B2条件数为6.34796。
- 完成141项基础检查、63项运行检查、318次pilot求解及5382次full求解，无失败解。全体KKT最大违反量约4.04×10^-16。独立面积守恒误差约3.33×10^-16。
- B2相对归一原ROI的detector额外视场损失为0.032599%–0.182200%；与原512μm ROI未收集的全域能量是两个不同量。

以下为shape_only、18条光谱、噪声条件3个固定种子的平均NRMSE；详细均值/中位数/最坏例及种子SD见原表。

|协议/条件|B0普通RGB|B1固定PSF|B2多波长PSF|
|---|---:|---:|---:|
|Q：实际SNR 30dB|0.46724|0.46743|0.00033639|
|Q：实际SNR 40dB|0.46701|0.46707|0.00010637|
|P：P_in=10⁴，read=1e RMS|0.51127|0.59564|0.055376|
|P：P_in=10⁴，read=3e RMS|0.51516|0.63255|0.090776|
|P：P_in=10⁵，read=1e RMS|0.47651|0.48872|0.014753|
|P：P_in=10⁵，read=3e RMS|0.47689|0.49556|0.016746|

Q的各模型实际阵列SNR误差不超过7.11×10^-15dB。P采用共同的模拟电子比例、相同入射预算；不同模型实际SNR不同，不能混作Q。所有电子尺度与1/3e读噪均为声明的模拟情景，不是实测相机参数。

23个失配条件仅改变A_true，M1固定标称A重建，M2为oracle诊断。无噪声下，x向+0.5像元偏移、最大0.25像元谱相关偏移、0.5像元Gaussian宽度、+5%固定RGB增益签名分别产生平均NRMSE约0.04978、0.02881、0.02248、0.03742。最坏M1为y向-0.5像元偏移的630nm单峰，NRMSE约0.12132。增加精确模型下的SNR不能消除这些标定失配。

shape_only与throughput-aware分别成表；后者统一向三模型外加同一B2有限域收集份额q(λ)，只计一次，不能解释为各硬件本身的真实效率。低预算/高读噪下throughput-aware B2最坏NRMSE约0.38645，负结果完整保留。

25带**仅矩阵诊断，无恢复**：秩25、条件数1439.91、最大邻列余弦0.96273、熵有效秩6.759。数值满秩不能掩盖小奇异值导致的高敏感性。

## 图表与机器可读结果

- [面积采样前后PSF](figures/sampling_psf_comparison.png)、[9带奇异值](figures/singular_values_9band.png)。
- [失配NRMSE](figures/mismatch_nrmse_log.png)、[失配SAM](figures/mismatch_sam_log.png)。
- [P/Q预算对照](figures/noise_budget_comparison.png)、[最好/中位/最坏谱例](figures/spectrum_best_median_worst.png)。
- [25带专用诊断图](figures/diagnostic_25bands_verified.png)。原`diagnostic_25bands.png`带通用9带模板副标题，请使用此专用图；没有25带NNLS。
- `metrics.csv`、`summary_metrics.csv`、`spectral_solutions.json`：完整逐例真谱、估计、指标和统计。
- `model_mismatch.csv`、`perturbation_manifest.json`、`mismatch_ratios.csv`：失配参数、真矩阵变化及M1/M0比值。
- `noise_calibration.csv`、`throughput_analysis.csv`、`sampling_energy_check.csv`、`independent_energy_verification.csv`：预算、电子数和能量证据。
- `run_config.json`、`input_manifest.json`：预注册契约、环境、Git状态、波长/RGB映射、随机种子及输入哈希。

## 新代码与停止位置

新增代码仅位于`E:/SH/integration/single_spiral_to_hsi/n03_exp2/`，包含面积积分、前向、扰动、噪声、统计绘图、实验入口及交付复核；新增测试为`E:/SH/integration/single_spiral_to_hsi/tests/test_n03_exp2.py`。没有修改EXP1、N02、DeepLens、原PSF/高度/mask或用户README，没有删除、清理、提交或推送。

首次pilot暴露的欠定NNLS问题采用补全零观测行解决，目标函数严格不变；最终扰动采用连续源像元→detector积分，Gaussian以解析双面积积分并用独立数值积分校验。失败与早期版本均保留，未以放宽KKT门或挑选光谱解决问题。

**下一阶段判定：CONDITIONAL GO。** 9带归档模型在本次噪声与采样下有探索性增益，但标定失配和25带病态风险明确。建议先补位置/RGB标定及独立物理数值认证；不自动放行25带恢复、未知点位、多点/整幅场景、双孔径或DOE优化。到此停止，提交ChatGPT审核。
