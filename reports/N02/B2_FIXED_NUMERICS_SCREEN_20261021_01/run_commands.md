# 实际命令与复跑

EXP2B EXPLORATORY, archived PSFs; N03 G0 FAIL; N02 G2/G3_Numerics FAIL.

工作目录E:\SH，实际命令：

```powershell
D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B integration/single_spiral_to_hsi/n03_exp2b/run_boundary_screen.py --output E:\SH\reports\N02\B2_FIXED_NUMERICS_SCREEN_20261021_01
```

复跑必须另选尚不存在的输出目录；OPENBLAS_NUM_THREADS、MKL_NUM_THREADS、OMP_NUM_THREADS均为4，PYTHONDONTWRITEBYTECODE=1，既有环境，无依赖安装。
