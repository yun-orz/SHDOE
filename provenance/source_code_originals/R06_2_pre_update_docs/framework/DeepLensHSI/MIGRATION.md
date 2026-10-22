# 本工作树迁移说明

这是2026-10-20对源B当前工作树的精选快照，保留未提交修改的实际字节；原Git不在此目录。原README署名与CC BY-NC 4.0声明保持原文。

仅含8个CAVE验证场景、nafnet_hsi预训练参数和原光学/传感器输入；训练集和额外光学示例未纳入。README中assets/video1_raw.gif等展示媒体及训练入口的非验证资源不在本次范围。

reference_results/R05_validation是旧R05原始参考；results/R05_validation是本次重新编码、推理与评价的新结果。8场景GT、pred和指标均与历史参考完全一致。原5/6脚本未改，固定输出位置已有结果，不应直接复跑覆盖；后续应先增加新输出目录参数。

环境、实测命令及最终限制见E:/SH/environments/README.md与E:/SH/provenance/migration_reports/final_report.md。
