# SH：单孔径 DOE 与高光谱研发工作区

迁移日期：2026-10-20。已补充R06-2通道对齐基线（同日）。迁移验收结论：**PASS_WITH_KNOWN_LIMITATIONS**。本目录保留当前工作树快照，不包含旧仓库的 `.git`，现已建立本地Git仓库，当前基线标签为`sh-r06-2-ready-20261020`，未自动push。

## 实测结果与科研状态

| 模块 | 本次独立验收 | 数值对照 |
|---|---|---|
| N00 多波长前向 | T01–T06 PASS | 31×512×512；与冻结参考PSF、原始强度最大差均为0 |
| DeepLensHSI 当前R06-2通道对齐基线 | 8场景重新编码、推理及评价 PASS；网络入口RGB→BGR | 平均PSNR 30.819418430 dB、SSIM 0.849800、固定GT掩膜SAM 21.931973815°、历史双有效掩膜SAM 17.079047561°；与原R06-2逐场景指标最大绝对差7.63e-6 |
| 历史R05基础对照（保留） | 原18.1866dB结果归档 | 不再作为当前默认基线；旧指标与张量保留用于解释通道顺序问题 |
| N02 固定候选与R/R2证据 | 导入、固定输入、哈希、数值复核 PASS | 25波长指标重算误差0；R2完整55项输入、9项源码可追溯；54项原产物SHA一致 |

以上迁移验收均在Python审计钩子屏蔽两个旧工程路径后完成（源侧parity对照除外）。路径屏蔽不等同操作系统ACL隔离。已有环境位于D盘，不代表已在新主机重装环境验证。

**N02的G2/G3仍FAIL；G4–G8未测试。** R默认查阅`reports/n02_1c_r/n02_1cr_20261020_01/summary_v2.md`，状态INCONCLUSIVE；旧summary与gate decision一并保留。R2为LOCAL_MECHANISM_SUPPORTED_GLOBAL_INCONCLUSIVE，不能表述成成熟PSF或新DOE端到端已复现。材料Cauchy曲线为假设，非IP-Dip2实测。未启动新的DOE优化或16×16 RS求积。

## 目录

- `framework/DeepLensHSI/`：精选推理源码、预训练参数、原光学与传感器配置、8个CAVE验证样例。原README保留署名及CC BY-NC 4.0声明。
- `framework/DeepLensHSI/reference_results/R05_validation/`：旧R05原始参考；`results/R05_validation/`为本次新推理结果。
- `optics/n00_forward/`：N00源码、配置、测试、文档；`reference_results/N00_verified/`为冻结参考，`results/migration_20261020/`为新正式输出。
- `optics/n02_single_spiral/`：三个N02分支。为兼容原相对路径，精选参考保留在`results/n02*`，没有改名为`reference_results`。这些冻结结果不要作为新输出目录。
- `optics/n02_single_spiral/vendor_compat/`：仅8个旧Python文件与所需N00光学库，不含N01旧结果。旧文件内未调用的C型构造暂留，不代表迁入C型研究分支。
- `integration/single_spiral_to_hsi/INTERFACE_PLAN.md`：待开发接口设计，没有把新N02 PSF接入重建。
- `environments/`：实测版本与可解析依赖清单；不复制整套conda环境。
- `provenance/`：源Git状态、逐文件哈希、候选清单、原输入解析、依赖图、代码差异与最终报告。

## 使用与复核

PowerShell中优先使用已核验环境：

```powershell
$py = 'D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:MPLCONFIGDIR = 'E:\SH\provenance\runtime_cache\matplotlib'
$env:TORCH_HOME = 'E:\SH\provenance\runtime_cache\torch'
$env:PYTHONPATH = 'E:\SH\provenance\guard'
```

N00回归及正式输出（`--output`必须选择尚不存在的新目录）：

```powershell
Set-Location E:\SH\optics\n00_forward
& $py -B tests/run_all_tests.py
& $py -B scripts/run_n00_psf.py --output E:\SH\optics\n00_forward\results\my_new_run
```

N02固定输入复核（输出JSON必须尚不存在；不启动新研究计算）：

```powershell
& $py -B E:\SH\provenance\tools\verify_n02_frozen.py E:\SH\optics\n02_single_spiral E:\SH\provenance\migration_reports\my_n02_verification.json --guard
```

DeepLens本次真实执行的是子目录中的`5_eval_pretrained.py --limit 8`和`6_evaluate_metrics.py`，这是更新前的R05验证记录；更新后脚本默认输出为`results/R06_2_validation`，并支持`--output`。该位置已有本次结果，**不要直接重复执行并覆盖**。更新后5/6脚本已支持自定义输出路径并拒绝覆盖；当前默认使用R06-2 BGR约定，结果见`results/R06_2_validation/metrics.csv`。R05结果保留为历史对照。

完整命令、耗时及退出码见`provenance/migration_reports/*_command.json`；报告见`provenance/migration_reports/final_report.md`。

## 已知边界

旧N02/R的整包审计会要求所有历史变体与N01历史结果，本次精简后不支持重跑该历史审计。R2旧命令行校验器仍按旧绝对路径和原源码哈希工作，改用本工作区的固定输入入口及`R2_input_resolution.json`映射。历史文档、manifest内的旧路径保留原文用于溯源，不能机械地全替换。

`n00_forward/scripts/snapshot_reference.py`已显式停用；旧`build_report.py`是依赖旧双输出目录布局的历史工具，本次不重跑。新的迁移报告独立生成。训练集、其他光学模型及训练复现不在本次范围。


## 当前默认重建基线：R06-2

原相机仍输出物理RGB，推理前按`encoded_rgb[:, [2,1,0], :, :]`适配网络输入。开关为`configs/1_deeplens_hsi.yml`中的`network.swap_rgb_channels: true`；没有修改nafnet_hsi.pth、传感器曲线、GT或31谱通道顺序。仅此处的5/6验证入口为本次更新的主入口；原1/3训练/演示脚本保留来源版本，不要据其旧默认行为判断当前基线。

从DeepLensHSI子目录执行；下面两条命令必须选择尚未使用的新输出路径：

```powershell
Set-Location E:\SH\framework\DeepLensHSI
& $py -B 5_eval_pretrained.py --limit 8 --output results/my_r06_run
& $py -B 6_evaluate_metrics.py --input results/my_r06_run
```

`--no-swap-rb --output results/my_rgb_control`可显式回到RGB对照；不改变默认配置。评价表`sam_deg`沿用历史双有效掩膜SAM，`sam_fixed_deg`为固定GT掩膜SAM（GT有效但预测为零按90°计）。30.8194dB为8场景PSNR算术平均，不是全局MSE聚合PSNR（原R06-2约28.2027dB）。

原证据完整迁入`framework/DeepLensHSI/reports/R06-2_channel_swap/`；新验证与差异报告见`provenance/migration_reports/R06_2_baseline_update.md`。
