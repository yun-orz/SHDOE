# EXP1

EXPLORATORY ONLY — archived B2 PSF numerical-convergence certification is incomplete; results do not establish physical DOE performance.

EXP1-A/B/C完成；只验证归档数值PSF的点源谱反演，原G0 FAIL保持不变。数值结论见result_summary.md。

工作目录E:\SH，使用已有环境；先将OMP_NUM_THREADS、MKL_NUM_THREADS、OPENBLAS_NUM_THREADS设为4。新输出目录必须尚不存在。

```powershell
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B E:\SH\integration\single_spiral_to_hsi\n03_exp1\run_exp1.py --output E:\SH\reports\N03\EXP1_replay_unique
```

入口先运行全部基础检查，不通过即STOP-E；通过才运行实验。精确实际调用与环境见logs/run_record.json。
