EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL

H5_DIAG_MIXED

旧EXP3R H2/H3/H4 PASS、H5 FAIL、full NOT_RUN 0/504永久保留。

实际阶段：{"D0": true, "D1": true, "D2": true, "D3": {"status": "D3_SKIPPED", "reason": "D1来源回放与D2成功终点对照已提供两类机制的逐例定量证据；无需用新优化分辨主要案例。", "new_starts": 0, "new_function_evaluations": 0, "NNLS_calls": 0}}

Observed：{
  "B_observations": 48,
  "B_local_starts": 96,
  "H5_exact_replay": 8,
  "provenance_counts": {
    "SUCCESSFUL_START_INTERMEDIATE": 28,
    "UNSUCCESSFUL_START_ONLY": 12,
    "SUCCESSFUL_RETURN_ENDPOINT": 8
  },
  "C1_available": 47,
  "no_successful_endpoint_cases": [
    "pilot_4_9_0"
  ],
  "new_optimization_starts": 0
}

Diagnostic inference：{
  "semantic_close_cases": [
    "pilot_0_0_0",
    "pilot_0_8_0",
    "pilot_0_8_20261021",
    "pilot_0_9_0",
    "pilot_0_11_0",
    "pilot_0_13_0",
    "pilot_0_15_0",
    "pilot_0_15_20261021",
    "pilot_1_0_20261021",
    "pilot_1_8_0",
    "pilot_1_8_20261021",
    "pilot_1_9_20261021",
    "pilot_1_11_0",
    "pilot_1_11_20261021",
    "pilot_1_13_0",
    "pilot_1_15_0",
    "pilot_1_15_20261021",
    "pilot_3_0_20261021",
    "pilot_3_8_0",
    "pilot_3_8_20261021",
    "pilot_3_11_0",
    "pilot_3_11_20261021",
    "pilot_3_13_0",
    "pilot_3_15_0",
    "pilot_3_15_20261021",
    "pilot_4_0_0",
    "pilot_4_0_20261021",
    "pilot_4_15_20261021"
  ],
  "convergence_limited_cases": [
    "pilot_4_9_0"
  ],
  "unresolved_cases": [
    "pilot_0_0_20261021",
    "pilot_0_13_20261021",
    "pilot_1_9_0",
    "pilot_3_0_0",
    "pilot_3_9_0",
    "pilot_4_9_20261021",
    "pilot_4_11_0",
    "pilot_4_11_20261021",
    "pilot_4_13_0",
    "pilot_4_13_20261021",
    "pilot_4_15_0"
  ],
  "rule": "多数未认证中间点接近成功终点且目标接近支持语义；无成功终点或failure-only点与成功终点有显著距离/目标差支持收敛限制。"
}

C0/C1 clean/Q40统计（均分列mean/median/P90/max，缺失终点不进入有效样本统计）：

```json
{
  "protocol": "noiseless",
  "group": "ALL",
  "total": 24,
  "C1_valid": 23,
  "no_endpoint": [
    "pilot_4_9_0"
  ],
  "C0_position_error_px": {
    "n": 24,
    "mean": 7.748824560679895e-08,
    "median": 1.0364610219071546e-09,
    "p90": 2.7303614354819326e-07,
    "max": 7.345858150768335e-07
  },
  "C0_NRMSE": {
    "n": 24,
    "mean": 8.475759363153098e-09,
    "median": 1.5597908054455307e-11,
    "p90": 2.7536712100382643e-08,
    "max": 8.425974917195397e-08
  },
  "C0_SAM_deg": {
    "n": 24,
    "mean": 7.62091156941328e-07,
    "median": 0.0,
    "p90": 1.6985926182092153e-06,
    "max": 4.829673078902934e-06
  },
  "C0_objective": {
    "n": 24,
    "mean": 1.3804250199999846e-15,
    "median": 9.072395149811183e-20,
    "p90": 2.0481787550990994e-15,
    "max": 1.9420076232833628e-14
  },
  "C1_position_error_px": {
    "n": 23,
    "mean": 1.597865598267528e-07,
    "median": 5.5155228706222044e-08,
    "p90": 4.450462782497441e-07,
    "max": 7.465903885911569e-07
  },
  "C1_NRMSE": {
    "n": 23,
    "mean": 1.780190531025293e-08,
    "median": 1.7180596010684306e-09,
    "p90": 6.412692581817117e-08,
    "max": 8.563894127092533e-08
  },
  "C1_SAM_deg": {
    "n": 23,
    "mean": 1.1615063452133338e-06,
    "median": 8.537736462515939e-07,
    "p90": 3.795154425948752e-06,
    "max": 4.829673078902934e-06
  },
  "C1_objective": {
    "n": 23,
    "mean": 2.5234622968300076e-15,
    "median": 1.0852695932803391e-16,
    "p90": 5.411422276772425e-15,
    "max": 2.006061375940985e-14
  },
  "C1_NRMSE_le_0.01_valid_fraction": 1.0,
  "C1_NRMSE_le_0.01_all_denominator_fraction": 0.9583333333333334,
  "position_shift": {
    "n": 23,
    "mean": 8.369321011813509e-08,
    "median": 1.9381111208701926e-08,
    "p90": 2.631905748797032e-07,
    "max": 4.037563477458601e-07
  },
  "objective_regret": {
    "n": 23,
    "mean": 1.0862288492464587e-15,
    "median": 1.693581912269481e-17,
    "p90": 3.559525706450221e-15,
    "max": 6.275021409990382e-15
  },
  "C1_position_threshold_exceed_cases": []
}
```

```json
{
  "protocol": "Q40",
  "group": "ALL",
  "total": 24,
  "C1_valid": 24,
  "no_endpoint": [],
  "C0_position_error_px": {
    "n": 24,
    "mean": 0.00033311308201721085,
    "median": 0.0001898499160064622,
    "p90": 0.0006664142475780036,
    "max": 0.0007034698429688632
  },
  "C0_NRMSE": {
    "n": 24,
    "mean": 0.00012009921827710389,
    "median": 0.00013140984166748292,
    "p90": 0.00020586429269946267,
    "max": 0.00021476530073042817
  },
  "C0_SAM_deg": {
    "n": 24,
    "mean": 0.0056623754297787645,
    "median": 0.006051216534342206,
    "p90": 0.011793883588488848,
    "max": 0.012298538393089859
  },
  "C0_objective": {
    "n": 24,
    "mean": 9.998293867954889e-05,
    "median": 9.998698065266355e-05,
    "p90": 9.999364372151169e-05,
    "max": 9.999611549790196e-05
  },
  "C1_position_error_px": {
    "n": 24,
    "mean": 0.0003330753101971741,
    "median": 0.00018987815138974616,
    "p90": 0.0006664138847896087,
    "max": 0.0007034698414172117
  },
  "C1_NRMSE": {
    "n": 24,
    "mean": 0.00012010069653030559,
    "median": 0.00013140965718285976,
    "p90": 0.0002058687593551469,
    "max": 0.00021476530563666459
  },
  "C1_SAM_deg": {
    "n": 24,
    "mean": 0.005662447433392048,
    "median": 0.006051214009246738,
    "p90": 0.0117941383073447,
    "max": 0.012298538630168256
  },
  "C1_objective": {
    "n": 24,
    "mean": 9.998293868141251e-05,
    "median": 9.998698065267243e-05,
    "p90": 9.999364372899597e-05,
    "max": 9.999611549790196e-05
  },
  "C1_NRMSE_le_0.01_valid_fraction": 1.0,
  "C1_NRMSE_le_0.01_all_denominator_fraction": 1.0,
  "position_shift": {
    "n": 24,
    "mean": 7.518083332374283e-08,
    "median": 4.826706422776895e-10,
    "p90": 2.9381078811244734e-07,
    "max": 6.168725917672015e-07
  },
  "objective_regret": {
    "n": 24,
    "mean": 1.8636113973628105e-15,
    "median": 6.776263578034403e-20,
    "p90": 5.699259152721485e-15,
    "max": 1.9464464762197764e-14
  },
  "C1_position_threshold_exceed_cases": []
}
```

真实可继续下降的直接证据：D2没有新优化，C1通常只能维持或增加C0的目标；未据此证明C0还能下降。缺少成功终点/预算耗尽只证明收敛认证受限。D3结果以D3_status为准。

原始逐例：provenance_audit.csv、termination_audit.csv、endpoint_only_comparison.csv、D2_objective_reverification.csv；旧H5逐字规则original_H5_verbatim.txt；精确回放h5_exact_replay.json。

工程QA：True；输入input_manifest；源码source_manifest与logs/source_snapshot；全部交付哈希final_manifest.json。

Unverified：光学PSF可信性和真实相机标定；全域唯一性；单seed以外的噪声泛化；未精修案例是否还能下降。

若独立审核确认这些来源和C1反事实，另立并预注册候选返回/收敛认证一致的单点pilot；本轮不改旧选择器、不放行full。


本轮补充独立核验：True。五类状态分列见case_diagnostic_labels.csv。

最差案例（有效覆盖分母与全体分母分列，无成功终点不伪装成功）：

|协议|策略|指标|case ID|值|有效/全体|
|---|---|---|---|---:|---:|
|noiseless|C0|position_error_px|pilot_1_15_0|7.34585815077e-07|24/24|
|noiseless|C0|NRMSE|pilot_1_15_0|8.4259749172e-08|24/24|
|noiseless|C0|SAM_deg|pilot_1_15_0|4.8296730789e-06|24/24|
|noiseless|C1|position_error_px|pilot_1_15_0|7.46590388591e-07|23/24|
|noiseless|C1|NRMSE|pilot_1_15_0|8.56389412709e-08|23/24|
|noiseless|C1|SAM_deg|pilot_1_15_0|4.8296730789e-06|23/24|
|Q40|C0|position_error_px|pilot_3_8_20261021|0.000703469842969|24/24|
|Q40|C0|NRMSE|pilot_4_15_20261021|0.00021476530073|24/24|
|Q40|C0|SAM_deg|pilot_4_15_20261021|0.0122985383931|24/24|
|Q40|C1|position_error_px|pilot_3_8_20261021|0.000703469841417|24/24|
|Q40|C1|NRMSE|pilot_4_15_20261021|0.000214765305637|24/24|
|Q40|C1|SAM_deg|pilot_4_15_20261021|0.0122985386302|24/24|
