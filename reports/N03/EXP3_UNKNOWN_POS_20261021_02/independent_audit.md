# EXP3独立复核

EXPLORATORY ONLY / optical G0 FAIL — archived B2 optical PSF is not full-domain numerically certified; image-plane shift-invariance is an approximation

独立密集几何积分、半像元边界、EXP2连续高斯API、两例复跑与原点退化检查：PASS。统计逐行回算、输入/源码/原始产物哈希、O/F/J同噪声与样本完整性核验通过。

[
  {
    "protocol": "noiseless",
    "n": 24,
    "J_less_NRMSE_than_F_fraction": 0.75,
    "F_minus_J_NRMSE_mean": 0.01899265433901041,
    "F_minus_J_NRMSE_median": 0.009538344348894456,
    "J_minus_O_NRMSE_mean": 9.677486182487452e-05,
    "J_minus_O_NRMSE_median": 7.3536989245531285e-09,
    "J_over_F_NRMSE_median_excluding_numerical_zero_F": 1.4519054906338295e-06
  },
  {
    "protocol": "Q40",
    "n": 24,
    "J_less_NRMSE_than_F_fraction": 0.9166666666666666,
    "F_minus_J_NRMSE_mean": 0.01891584327232805,
    "F_minus_J_NRMSE_median": 0.009446179640036838,
    "J_minus_O_NRMSE_mean": 0.00010020313681916487,
    "J_minus_O_NRMSE_median": -1.985721972963539e-07,
    "J_over_F_NRMSE_median_excluding_numerical_zero_F": 0.013568904749989733
  }
]

局部优化终止统计：{"total": 96, "converged": 19, "budget_terminated": 77}。预算终止保留其最好候选；不属于内层NNLS失败，也不证明达到连续极小值。所有例子均遵守119候选预算，未追加优化轮次。最坏定位案例与局部目标动态图幅见independent_audit.json；有限采样不认证全域唯一性。
