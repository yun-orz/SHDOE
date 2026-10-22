# 单孔径 DOE 多波长 PSF：N00

当前仅做固定高度→多波长色散相位→标量 ASM→PSF 的计算基座验证，不执行 N01/N02。

工程位于 `E:/SpiralDOE_HSI/n00_run_20261009`，独立 Git；父目录历史中有已删除的用户文件，因此不恢复或覆盖父目录内容。参考库 `E:/DeepLensHSI` 只读，不导入其模块。

在 PowerShell 执行：

```powershell
Set-Location E:\SpiralDOE_HSI\n00_run_20261009
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' scripts/run_n00_psf.py --output results/N00_reproduce
```

首次执行可省略 `--output`；正式产物存在时不会覆盖。复跑路径必须不存在。先顺序运行 T01–T04 小测试及收敛检查，通过后生成 31 波段，并检查 T05/T06。前置测试记录写入 `results/N00/preflight_summary.json`，各次正式产物存所指定目录。既有前置记录可能更新，正式 NPZ/报告不覆盖。

参数见 `configs/n00_baseline.yaml`，环境锁定见 `requirements.txt` 和 `docs/evidence`。接口、单位、边界见 `docs/N00_interface_audit.md`；最终验收报告在 `reports/N00`。
