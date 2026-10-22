# 首次审计尝试异常记录

实际命令：

```powershell
& 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe' -B integration/single_spiral_to_hsi/n03_audit.py --output E:\SH\reports\N03
```

退出码1。在遍历历史B2/frozen_sha256.json时，脚本把完整旧清单误当作精选迁移后的现存文件集合，遇到未迁入的435nm诊断文件：

```text
FileNotFoundError: [Errno 2] No such file or directory:
E:\SH\optics\n02_single_spiral\results\n02\n02_20261019_02\B2\cases\435nm.npz
```

失败发生在创建输出目录前，没有写入或覆盖任何报告。随后修正脚本：现存文件逐项校验原SHA，未迁入项写入manifest的historical_frozen_manifest_missing_files，不以全包PASS掩盖缺项。第二次实际运行退出码0，结果见00_audit_run.json。无删除或补造缺失PSF。
