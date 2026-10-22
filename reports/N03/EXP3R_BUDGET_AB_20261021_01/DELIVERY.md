EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL

EXP3R_PILOT_FAIL；full NOT_RUN（0/504）。

A/B各目标48观测；实际 {'A': 48, 'B': 48}。

H0–H6：{"H0": {"passed": true, "definition": "48观测指纹一致且A的144行历史回归通过"}, "H1": {"passed": true, "definition": "仅maxfev55→150；真值隔离；同一只读y"}, "H2": {"passed": true, "passed_cases": 24, "total": 24, "threshold": 0.005}, "H3": {"passed": true, "passed_cases": 24, "total": 24, "threshold": 0.02}, "H4": {"passed": true, "fractions": {"noiseless": 1.0, "Q40": 1.0}, "NRMSE_threshold": 0.01, "fraction_threshold": 0.8}, "H5": {"passed": false, "accepted": 8, "total": 48, "definition": "选中缓存点与成功Powell返回终点逐位相同，且NNLS有限非负/KKT合格"}, "H6": {"passed": true, "unchanged": true, "complete": true, "boundary_cases": [], "OF_invariant": true}}

A noiseless: position mean/median/P90/max=0.00121296662637/1.91788007148e-07/0.00449339646368/0.0117160999959 px；NRMSE median/max=7.35370251832e-09/0.00101407247562。

A Q40: position mean/median/P90/max=0.00149253877119/0.000239122096837/0.00515579424092/0.0118376109534 px；NRMSE median/max=0.000160238291811/0.000980865833549。

B noiseless: position mean/median/P90/max=7.74882456068e-08/1.03646102191e-09/2.73036143548e-07/7.34585815077e-07 px；NRMSE median/max=1.55979080545e-11/8.4259749172e-08。

B Q40: position mean/median/P90/max=0.000333113082017/0.000189849916006/0.000666414247578/0.000703469842969 px；NRMSE median/max=0.000131409841667/0.00021476530073。

优化器：{"A": {"observations": 48, "local_starts": 96, "converged_starts": 19, "budget_exhausted_starts": 77, "selected_converged": 0, "maximum_unique_evaluations": 117}, "B": {"observations": 48, "local_starts": 96, "converged_starts": 77, "budget_exhausted_starts": 19, "selected_converged": 8, "maximum_unique_evaluations": 307}}

A/B共享只读观测，noise/y指纹见 observations_manifest.json；A历史逐例和轨迹回归见 archived_A_regression.csv / archived_A_trace_regression.json。

原始288行（完整执行时）、配对统计与全部局部终止分别见 ab_metrics.csv、paired_improvement.csv、optimizer_terminations.csv；代码快照在 logs/source_snapshot；最终SHA256在artifact_manifest.json。

N03 G0 FAIL；N02 G2/G3_Numerics FAIL。单seed Q40，无P预算；同模型shape_only合成恢复，不认证物理精度。局部图后验计算且没有回流Joint，不证明全局唯一性。没有追加B重试、full或参数扫描。等待ChatGPT经Bridge只读审核。
