# 当前Git基线

本仓库的首个基线标签为 `baseline-r06-2-20261020`，包含R06-2通道对齐后的代码、配置、预训练权重、8场景验证数据、N00/N02参考、重建结果、迁移报告及来源证据。

本地Git提交保存实际文件内容，不只保存复制清单或哈希。原始E:/DeepLensHSI及E:/SpiralDOE_HSI不属于本仓库，也不会被这里的Git操作修改。没有自动推送到远端。

`.git`自身、Python字节码和provenance/runtime_cache等可再生成缓存不属于科研基线。原子工程的.gitignore保留，因此初次提交对其默认忽略的模型、数据及结果显式逐文件加入；之后这些已有文件的变化仍可由Git跟踪。以后新增的结果若命中子工程忽略规则，需要明确加入。

本仓库通过.gitattributes禁用自动换行转换，首个提交须逐文件比对Git blob与工作区字节后才宣告可回退。

查看基线和后续变化：

```powershell
git -C E:\SH status
git -C E:\SH log --oneline --decorate -5
git -C E:\SH show baseline-r06-2-20261020:README.md
```

基线建立后新增或修改的工作需另行提交才形成新的回退点。恢复操作应先保存尚未提交的工作；任何涉及删除的动作仍须先征得用户明确同意。


当前最终基线标签：`sh-r06-2-ready-20261020`。首次入库标签`baseline-r06-2-20261020`同时保留；最终标签另包含Git使用说明更新。

已在本仓库设置maintenance.auto=false、gc.auto=0、gc.autoPackLimit=0，避免提交自动触发清理。首次提交自动启动的对象维护已停止，保留其临时文件，不执行未经许可的删除。
