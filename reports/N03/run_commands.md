# 复跑命令

工作目录E:\SH；输出目录须尚不存在，脚本拒绝覆盖。

```powershell
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B E:\SH\integration\single_spiral_to_hsi\n03_audit.py --output E:\SH\reports\N03_recheck_unique
```

只读输入；仅向指定新目录写审计报告。无环境安装、无传播或重建。
