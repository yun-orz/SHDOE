# R06-2当前重建基线更新验收

日期：2026-10-20。状态：**PASS**。用户指出旧迁移只选择了R05基础版本，本次将R06-2作为当前默认推理基线。

## 实测结果

平均PSNR 30.819418430 dB、SSIM 0.849800、固定GT掩膜SAM 21.931973815°、历史双有效掩膜SAM 17.079047561°。8/8场景PSNR优于旧R05，8场景平均PSNR提升约12.6328dB。30.8194dB是逐场景dB的算术平均；原受控实验的全局MSE聚合PSNR是28.2027dB，应区分统计方式。

原R06-2历史结果：PSNR30.819419860840dB、SSIM0.8498、固定GT掩膜SAM21.931971549988°、历史双有效掩膜SAM17.079045772552°。本次各场景各指标最大绝对差7.62939453125e-06，均小于事先设定1e-4容差；PSNR最大差3.8146973e-6dB。差异处在GPU/CPU归约和no_grad/inference_mode路径的浮点舍入量级；没有为通过而调宽容差。

## 实现与来源

- 原reports/R06-2_channel_swap目录14个文件共5347222字节先形成干运行清单，再复制并逐项验证SHA相同。包含报告、脚本、图、指标、日志和evidence；历史文档路径不替换。
- 改动仅新工作区的配置、5_eval_pretrained.py与6_evaluate_metrics.py，保存适配前原始字节及完整diff。
- 配置network.swap_rgb_channels=true；5在model前将encoded_rgb按[2,1,0]排列。权重文件不变，物理RGB和GT不变。默认新输出results/R06_2_validation；支持--output、--swap-rb/--no-swap-rb。5拒绝已有输出目录；6支持--input/--output并拒绝已有CSV。
- 6保留历史sam_deg，新增sam_fixed_deg；固定GT掩膜中零预测按90°计。预训练checkpoint SHA：`4cc4c92d95064155b312a2ff5dcf8037a5a431a2200f797d71f014e612d5666f`。
- 原1/3脚本保留来源版本；当前通道对齐主入口为5/6，不涉及重训。

## 执行与独立性

在E:/SH/framework/DeepLensHSI以Python3.10.22、torch2.5.1+cu121、RTX4060运行：

```powershell
& $py -B 5_eval_pretrained.py --limit 8
& $py -B 6_evaluate_metrics.py
```

两命令由record_run.py设置旧源路径屏蔽后执行，8场景均成功。对应日志和耗时为R06_2_updated_inference.log/command.json及R06_2_updated_metrics.log/command.json。source_R06_2_update_verification为只读源完整性检查，刻意不启用路径屏蔽，与独立推理证据分开。

输出保护另测默认BGR推理、--no-swap-rb旧RGB路由及评价CSV拒绝覆盖，检查现有文件SHA未改变，详见R06_2_output_protection.json。

## 文件与文档

旧R05结果、旧报告与迁移计数作为历史快照保留。主README切换到R06-2当前基线，最终迁移报告顶部增加本次补充；原报告全文及修改前文档均保留。没有删除操作。

新增/修改清单：provenance/manifests/R06_2_update_candidate_dry_run.csv、R06_2_update_copied_sha256.csv；代码差异见provenance/audit/R06_2_code_adaptations.patch。完整8场景数值差异、模型与数据保护结果见R06_2_baseline_update_verification.json。

## 源目录保护

本轮源B所有1344项文件的SHA-256、size、mtime_ns、文件清单和Git HEAD/status/暂存/未暂存diff/remote前后完全一致。290项已迁入的模型、光学、传感器、样例和历史参考也逐项SHA核对通过。旧源A本轮未操作；其先前完整保护证明仍保留。本次所有写入均位于E:/SH。

N02的G2/G3仍FAIL、R2全局结论未定；本次仅更新原DeepLens相机的重建基线，不改变新单孔径PSF尚未接入的状态。
