# EXP2运行命令

EXP2 exploratory; N02 G2/G3_Numerics=FAIL; N03 G0=FAIL. No certified physical DOE performance.

实际命令：

```powershell
D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B integration/single_spiral_to_hsi/n03_exp2/run_exp2.py --output E:\SH\reports\N03\EXP2_20261020_03
```

复跑，必须新输出目录：

```powershell
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
$env:OPENBLAS_NUM_THREADS='4'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B E:\SH\integration\single_spiral_to_hsi\n03_exp2\run_exp2.py --output E:\SH\reports\N03\EXP2_replay_unique
```

CPU，float64，既有环境，不安装依赖。完整实验先过G-impl及6谱pilot，才运行18谱full；25带只诊断。
