EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL

Observed：{
  "passed": true,
  "observations": 48,
  "starts": 96,
  "counts": {
    "SUCCESSFUL_START_INTERMEDIATE": 28,
    "UNSUCCESSFUL_START_ONLY": 12,
    "SUCCESSFUL_RETURN_ENDPOINT": 8
  },
  "successful_starts": 77,
  "budget_exhausted_starts": 19,
  "observations_with_successful_start": 47,
  "strict_H5_count": 8,
  "uncertified_float_near": 20,
  "mismatches": [],
  "original_gate": {
    "passed": false,
    "accepted": 8,
    "total": 48,
    "definition": "选中缓存点与成功Powell返回终点逐位相同，且NNLS有限非负/KKT合格"
  },
  "original_decision": "EXP3R_PILOT_FAIL",
  "old_H5_preserved": true
}

严格相同、浮点距离与目标差分别记录，任何新近似阈值均不回填原H5。真值误差仅为事后评分。
