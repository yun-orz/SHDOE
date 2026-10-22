# R06-2补充更新（2026-10-20，当前有效）

当前主入口为5_eval_pretrained.py和6_evaluate_metrics.py，默认网络输入BGR；平均PSNR 30.819418430 dB、SSIM 0.849800、固定GT掩膜SAM 21.931973815°、历史双有效掩膜SAM 17.079047561°。8场景实跑通过，原证据已迁入reports/R06-2_channel_swap，新的结果在results/R06_2_validation。模型权重、物理RGB响应和数据未改；支持--output避免覆盖。原1/3入口保持来源行为，不作为当前通道对齐验证入口。

以下为更新前R05迁移记录，保留溯源，其“脚本未改/不支持新输出参数”描述已被本次更新取代。

# 本工作树迁移说明

这是2026-10-20对源B当前工作树的精选快照，保留未提交修改的实际字节；原Git不在此目录。原README署名与CC BY-NC 4.0声明保持原文。

仅含8个CAVE验证场景、nafnet_hsi预训练参数和原光学/传感器输入；训练集和额外光学示例未纳入。README中assets/video1_raw.gif等展示媒体及训练入口的非验证资源不在本次范围。

reference_results/R05_validation是旧R05原始参考；results/R05_validation是本次重新编码、推理与评价的新结果。8场景GT、pred和指标均与历史参考完全一致。原5/6脚本未改，固定输出位置已有结果，不应直接复跑覆盖；后续应先增加新输出目录参数。

环境、实测命令及最终限制见E:/SH/environments/README.md与E:/SH/provenance/migration_reports/final_report.md。
