EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL

C1为离线反事实，先按原归档目标选成功返回终点，再使用相同y/模型/NNLS固定坐标重评价。没有新位置优化。

{
  "label": "H5_DIAG_MIXED",
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
  "uncertified_denominator": 40,
  "D3_needed": false,
  "rule": "多数未认证中间点接近成功终点且目标接近支持语义；无成功终点或failure-only点与成功终点有显著距离/目标差支持收敛限制。",
  "status": "D2_VERIFIED_COUNTERFACTUAL",
  "observations": 48,
  "C1_valid": 47,
  "no_endpoint_cases": [
    "pilot_4_9_0"
  ],
  "fixed_point_NNLS_calls": 116,
  "new_position_optimization_starts": 0,
  "objective_checks": 125,
  "all_objective_checks_pass": true,
  "old_H5_rejudged": false
}

按clean/Q40及来源分组的mean/median/P90/max见D2_decision.json的summary。无成功终点不回退C0；覆盖不完整不能作为完整替代策略。绝不重判旧H5/H2/H3。
