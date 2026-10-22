# EXP3结果：STOP_G3_2

EXPLORATORY ONLY / optical G0 FAIL — archived B2 optical PSF is not full-domain numerically certified; image-plane shift-invariance is an approximation

G3-0/G3-1 PASS；G3-2 FAIL；G3-3 NOT_RUN；G3-4 NOT_RUN；G3-5 PASS。

Algorithm implementation：连续面积积分、RGB、目标、KKT与原点oracle回归通过；候选预算119，所有局部终止原因及次优候选见optimization_traces。预算终止与NNLS失败分开记录，局部停止不证明全局最优。

Blind subpixel localization：pilot无噪声中位误差1.9178801e-07 pixel；Q40中位误差0.0002391221 pixel。像面nm换算乘2739.78685613；仅粗ROI已知的单点定位。

Spectral reconstruction：Q40中J的NRMSE≤0.01比例100.000%。各O/F/J中位与最坏值见paired_comparison.json；按类别、位置、seed的mean/median/P90/worst见comparison_summary.csv。最坏谱near_equal，位置ID=3，seed=0，NRMSE=0.0010140725。

Optical physics：N02 G2/G3_Numerics、N03 G0保持FAIL。无噪声为同模型自洽；失配24例仅为固定sigma=0.10 pixel合成展宽，O也使用错误名义模型，不代表实机性能。

pilot耗时105.39秒，峰值内存292.0MiB，预计full 1106.6秒；full预算3600秒。全部输入未改核验=True。目标函数二维图为最好/最坏定位案例局部17×17采样，不能排除采样间或全域其他极小值；第二候选仅为搜索中距离最优>0.01 pixel的候选，不是经认证的独立模态。


G3-2停止的直接依据：24幅无噪声pilot中，3幅位置误差超过0.005 pixel。最坏为near_equal，真位置(0.40,-0.35)，估计(0.39507837055,-0.36063224166)，误差0.0117161000 pixel（32.100 nm，仅像面换算）。同谱位置(-0.25,0.20)误差0.0088219951 pixel，broad_510在(0.40,-0.35)误差0.0056526260 pixel。具体计数与原始误差以metrics.csv、stop_diagnosis.json为准。

停止诊断：96个局部起点中19个正常收敛、77个耗尽各自55次预算；最坏无噪声案例两个起点均耗尽预算，真位置oracle残差更低。这说明当前冻结搜索预算内未稳定达到定位目标，不能据此断言物理不可辨识。未追加搜索、未改阈值、未删除难例。full与24例失配压力测试均NOT_RUN；上文有关sigma的文字描述预定方案，只有高斯API一致性单测实际执行。

独立复核：见[independent_audit.md](independent_audit.md)及[independent_audit.json](independent_audit.json)。输入、源码、逐行统计、同噪声配对、独立几何、两例复现均PASS。首次运行的JSON工程故障和唯一修复保留在相邻EXP3_UNKNOWN_POS_20261021_01/logs/failure_record.md；不将该故障目录视作实验结果。完整最终哈希以final_delivery_manifest.json为准。
