D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B integration/single_spiral_to_hsi/n03_exp3/run_exp3.py --output E:/SH/reports/N03/EXP3_UNKNOWN_POS_20261021_02

OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=4; PYTHONDONTWRITEBYTECODE=1
复跑必须指定新目录。

后处理实际命令（相同4线程环境）：

```powershell
& D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe -B integration/single_spiral_to_hsi/n03_exp3/audit_exp3.py E:/SH/reports/N03/EXP3_UNKNOWN_POS_20261021_02
& D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe -B integration/single_spiral_to_hsi/n03_exp3/verify_exp3.py E:/SH/reports/N03/EXP3_UNKNOWN_POS_20261021_02
```

另执行一次Python标准输入后处理：从metrics与optimization_traces提取最坏无噪声案例，重算oracle残差，输出stop_diagnosis.json；给result_summary与DELIVERY追加停止原因；从既有objective_maps.json生成带数值色标的objective_map_with_scale.png。此过程不重新优化、不改实验数据。原始必需5张图与补充图均已目视检查。
