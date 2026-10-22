# Git管理补充（2026-10-20，当前有效）

E:/SH现已建立独立本地Git仓库，代码、配置、权重、验证数据、参考与生成结果及来源证据均已纳入首个科研基线（排除可再生成缓存）。当前最终标签为`sh-r06-2-ready-20261020`，首次入库标签`baseline-r06-2-20261020`保留。未推送远端，未修改旧源仓库。本节取代下文历史报告中“未建立新Git”的状态说明。详见根目录GIT_BASELINE.md；字节校验记录存放于.git/baseline_verification.json。

# 当前补充：R06-2通道对齐基线（2026-10-20）

**当前DeepLensHSI默认基线已更新，8场景独立实跑PASS：平均PSNR 30.819418430 dB、SSIM 0.849800、固定GT掩膜SAM 21.931973815°、历史双有效掩膜SAM 17.079047561°。** 网络入口RGB→BGR，预训练权重和物理传感器不改；旧R05约18.18dB为基础历史对照。

新验收详见[R06_2_baseline_update.md](R06_2_baseline_update.md)，原R06-2证据在framework/DeepLensHSI/reports/R06-2_channel_swap。源B完整1344文件及Git状态前后不变。原808项复制计数与target_current_sha256.csv是更新前快照；增量14项原证据及新代码状态见R06_2增量清单和target_current_sha256_R06_2.csv。默认推理/评价已支持新输出路径并拒绝覆盖，旧文中的相应待办已解决。

N02原限制仍有效。以下原始迁移报告全文保留溯源，其中R05及“5/6脚本未改”等表述为更新前状态。

# SH精选迁移最终报告

日期：2026-10-20（Asia/Shanghai）。综合结论：**PASS_WITH_KNOWN_LIMITATIONS**。

## 1. 文件计数、总量、独立运行及数值对照

| 范围 | 文件数 | 字节数 | GiB |
|---|---:|---:|---:|
| 源A（含原Git与全部历史/缓存） | 7510 | 22633230761 | 21.078839 |
| 源B（含原Git） | 1344 | 1089878395 | 1.015028 |
| 两源合计 | 8854 | 23723109156 | 22.093867 |
| 主干运行清单 | 805 | 1309302726 | 1.219383 |
| 最终复制包（额外3份适配前源码证据） | 808 | 1309322634 | 1.219402 |
| 新工作区验收快照（含参考、新结果及审计工具；报告生成前） | 924 | 2082465008 | 1.939447 |

上述808个是复制项，包含为了保持模块相对路径而复制的小型src和原始源码证据，不等同于808个互不重复的源文件。另有任务书LF恢复副本和新建文档/结果，已计入工作区快照。工作区还将增加本报告等少量文本。

| 模块 | 独立运行结论 | 实测对照 |
|---|---|---|
| N00 | PASS；tests/run_all_tests.py及scripts/run_n00_psf.py通过T01–T06；测试子进程同样屏蔽旧源 | shape=31×512×512；400–700nm/10nm；归一化最大误差3.3306690738754696e-16；新旧PSF及raw强度最大差0；高度及波长完全相同 |
| N02精选候选 | PASS_WITH_KNOWN_LIMITATIONS；三个原入口可导入，新固定输入验证入口独立运行 | 25波长重算指标最大差0；源/新源场及complex128小ASM SHA相同；错误输入行为相同；R2 55项输入、9项源码本地完整SHA可追溯，54项原产物SHA一致 |
| DeepLensHSI原基线 | PASS；预训练参数strict加载、光学/传感器与CAVE读取成功，8场景原脚本重新编码、推理与评价 | 平均PSNR=18.186638236046 dB、SSIM=0.662075000、SAM=39.223211288452°；8场景GT、pred张量最大差及所有指标差均0 |
| 新N02 PSF→HSI闭环 | BLOCKED / 尚未开发 | 仅交付INTERFACE_PLAN.md；无新光学闭环成功声明 |

N00旧N00与N00_verified的NPZ文件SHA不同，键集合也不同，但共同的PSF、波长、高度、mask、坐标及raw强度逐数组最大差均0。只复制包含更完整坐标信息的verified参考。证据：N00_reference_deduplication.json、N00_source_array_deduplication.json。不能把容器字节不同误报为数值不同或哈希相同。

N02冻结高度完整文件SHA：`8166b58c358b3be2862cd9401f17b6bdd6ad5dcc575e5278aaa135f28b5ba19f`；mask SHA：`07e77628a12d6c223057b219d70a4eb5869027b139aaf4113f00cd0b40dc44bc`。R2独立补充复核重算84行ASM/RS残差、67组对边、5项物理峰比；同一原B006点q4全入瞳CPU/GPU复场绝对差2.2400628662900178e-20，相对差1.7067950767291383e-15。没有新增点/波长、16×16诊断或DOE优化。

图像检查：已查看新N00 psf_montage.png及DeepLens photo_and_face_ms/comparison.png，图像正常生成、坐标与场景布局可读。数值结论依据数组/指标比对，不以图像观感代替验收。

## 2. 阶段结果

- M00 PASS：先记录两源HEAD、remote、本地config、全部untracked与暂存/未暂存二进制diff，再对8854文件完整SHA/size/mtime盘点；无junction/symlink。主复制前再次核对Git与size/mtime一致。候选清单分类为{'COPY_REQUIRED': 792, 'REGENERATE': 153, 'LEAVE_SOURCE_ARCHIVE': 7906, 'REFACTOR_OR_VENDOR': 13}，COPY_OPTIONAL为0（本轮不选可选训练/展示资源）。复制前空闲空间约75.15GiB，大于复制量两倍，目标冲突0。
- M01 PASS：只复制8个CAVE验证样例；原预训练权重、planar_doe、相机与传感器配置齐全。保持源B当前工作树字节，未从旧HEAD还原。原README署名/CC BY-NC 4.0声明保留；本次不验证训练与其他光学示例。
- M02 PASS：T01–T06全部通过，原reference_results未覆盖。N00仅将Git读取改为保存的源HEAD；snapshot_reference历史写证据工具显式停用。新导出与参考完全一致。
- M03 PASS：当前三个N02分支的configs/experiments/reports和R/R2结果齐全；主N02精选B2而非整个2.90GiB变体包。R旧summary与v2同时保留，默认指向v2。R2失败run和最新run均保留；历史报告与manifest字面路径不改写。
- M04 PASS_WITH_KNOWN_LIMITATIONS：8个最小旧源码文件封装在vendor_compat，无旧N01结果；固定输入parity与路径屏蔽独立验证通过。函数级去C剥离尚未完成，属于兼容技术债，明确列在闭包审计中。
- M05 PASS_WITH_KNOWN_LIMITATIONS：总README、环境清单、接口设计、依赖图、哈希与最终报告齐全；没有新单孔径PSF到HSI的实现。

## 3. 状态与未解决事项

### PASS

必要模型、8场景数据、N00/N02固定输入均未发现缺失；所测数值无无法解释的漂移。复制时808项source/destination SHA一致；最终803项仍与源字节相同，5个已适配代码文件的当前SHA及文本diff分别见target_current_sha256.csv和code_adaptations.patch。改变的是路径/来源快照/归档工具保护，未改变阈值、单位、FFT/ASM、边界采样与归一化。

Python审计钩子屏蔽旧两个工程和个人Downloads，独立运行均成功。isolation_selftest证明两个源README读取均被PermissionError拒绝。该手段是Python文件访问路径屏蔽，不是操作系统ACL或恶意代码安全边界。依赖Python/torch及GPU驱动仍使用既有D盘环境。

### PASS_WITH_KNOWN_LIMITATIONS

1. vendor_compat文件内暂留未调用的W/C构造；安全函数级提炼尚未做，原因是动态导入绑定与混合模块。没有搬迁完整N01实验文件夹或旧结果。
2. 历史文档、hash清单和审计函数含旧绝对路径，这是来源证据；新固定验证通过映射解析。N02原audit、R全变体manifest审计、原R2命令行绝对路径校验器及N00旧build_report不支持直接作为新入口，详见dependency_graph.md。不是声称这些历史入口已独立全量重演。
3. 原DeepLens5/6脚本输出目录固定，源码保持原样；现有新输出目录已占用，勿直接复跑覆盖。尚未新增自定义输出参数。
4. 本次使用原匹配环境，不代表已在空白新主机安装验证。原requirements的packaging本地file URL保留为来源，在新requirements_runtime中改用实际distribution版本。原CUDA12.8 environment.yml与本次cu121环境区别已说明。
5. 少量本次Matplotlib缓存保存在provenance/runtime_cache，没有迁入旧pycache。目标无.git、*.pyc、__pycache__、悬挂链接或意外大历史目录；大文件清单见target_integrity_audit.json，均为参考与本次PSF/光谱产物。

### BLOCKED

- 新N02科学验收与端到端接入：原G2/G3仍FAIL，G4–G8未测试；R=INCONCLUSIVE；R2=LOCAL_MECHANISM_SUPPORTED_GLOBAL_INCONCLUSIVE。新PSF尚未接入DeepLens，无新闭环复现结论。
- 原整包历史重演：精简未带走被审计的所有参数变体/N01结果，因此旧审计函数需要的历史范围不具备；这是刻意保留在源仓库的归档范围。若未来要求重演，应另建限定清单，而非静默放宽哈希/门控。

没有待处理的预训练模型加载、8样例加载、N00数值或已选R2输入hash blocker。

## 4. 环境与实际命令

真实验收：Python3.10.22、torch2.5.1+cu121、torchvision0.20.1+cu121、NumPy2.2.6、SciPy1.15.3、RTX4060 Laptop GPU。完整包表见environments/runtime_versions.json。未安装、升级或移除依赖。

| 记录 | 工作目录 | 命令 | 退出码 | 耗时 | 旧源路径屏蔽 |
|---|---|---|---:|---:|---|
| DeepLens_R05_inference | `E:\SH\framework\DeepLensHSI` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B 5_eval_pretrained.py --limit 8` | 0 | 52.268s | 开启 |
| DeepLens_R05_metrics | `E:\SH\framework\DeepLensHSI` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B 6_evaluate_metrics.py` | 0 | 18.335s | 开启 |
| isolation_selftest | `E:\SH` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B E:\SH\provenance\tools\verify_guard.py` | 0 | 0.056s | 开启 |
| N00_export | `E:\SH\optics\n00_forward` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B scripts/run_n00_psf.py --output E:\SH\optics\n00_forward\results\migration_20261020` | 0 | 20.562s | 开启 |
| N00_tests | `E:\SH\optics\n00_forward` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B tests/run_all_tests.py` | 0 | 4.659s | 开启 |
| N02_extended | `E:\SH\optics\n02_single_spiral\experiments\n02_1c_r2` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B -c import r2_verify_extended as v,json;from pathlib import Path;r=v.verify(v.ROOT/'results/n02_1c_r2/n02_1cr2_20261020_02');p=Path('E:/SH/provenance/migration_reports/N02_extended.json');p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(r,ensure_ascii=False))` | 0 | 4.458s | 开启 |
| N02_frozen | `E:\SH` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B E:\SH\provenance\tools\verify_n02_frozen.py E:\SH\optics\n02_single_spiral E:\SH\provenance\migration_reports\N02_frozen.json --guard` | 0 | 4.640s | 开启 |
| reference_comparisons | `E:\SH` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B E:\SH\provenance\tools\compare_references.py` | 0 | 6.540s | 开启 |
| source_guard_selftest | `E:\SH` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B -c import os;from pathlib import Path;assert os.environ.get('SH_SOURCE_GUARD')=='1';n=0;exec('for p in [\ E:/DeepLensHSI/README.md\,\E:/SpiralDOE_HSI/n00_run_20261009/README.md\]:\n try:Path(p).read_bytes()\n except PermissionError:n+=1');assert n==2;print('SOURCE_GUARD_PASS',n)` | 1 | 0.036s | 未开启（源侧对照或未执行的失败调度） |
| source_N02_parity | `E:\SH` | `D:\MiniAnaconda\envs\deeplens_hsi_4060\python.exe -B E:\SH\provenance\tools\verify_n02_frozen.py E:\SpiralDOE_HSI\n00_run_20261009 E:\SH\provenance\migration_reports\source_N02_frozen.json` | 0 | 5.716s | 未开启（源侧对照或未执行的失败调度） |

所有运行日志保留在同名.log。source_guard_selftest首次是PowerShell传递-c字符串的引号错误（SyntaxError），没有执行项目代码；已改为独立verify_guard.py，isolation_selftest通过。失败记录保留，不覆盖掩盖。

数据迁移脚本依次为inventory_sources.py、select_candidates.py、precopy_check.py、copy_selected.py、adapt_targets.py、audit_resolution.py、audit_r2_source_hashes.py、verify_source_preservation.py、compare_references.py与final_integrity_audit.py；均在provenance/tools。主复制耗时17.485s；全源前后哈希比较耗时60.855s。源侧盘点首次耗时174.583s。最初冒烟另确认8场景、首例31×512×512、模型strict加载和相机初始化成功，后续独立完整8场景运行覆盖该检查。

## 5. 原工程原样保留的证明

source_preservation.json为PASS：源A7510项、源B1344项的**全部文件**（包含原Git文件）前后SHA-256、大小和mtime_ns完全相同；新增/缺失/变化列表均为空。A.txt/A_after.txt与B.txt/B_after.txt逐字相同，覆盖HEAD、remote、local config、全部untracked、暂存与工作区diff。

整个过程未删除、移动、清理或覆盖两源任何文件；未执行git reset/clean、robocopy MIR/MOVE/PURGE、格式化、push或新研究优化。两个原仓库及大批C/N01历史仍在原位置。本次只在E:/SH写入，未复制原.git，也未删除新目录里的任何内容。

## 6. 交付入口

- E:/SH/README.md
- E:/SH/provenance/migration_reports/final_report.md
- E:/SH/provenance/manifests/candidate_dry_run.csv 与 copied_files_sha256.csv
- E:/SH/provenance/manifests/target_current_sha256.csv
- E:/SH/provenance/source_git_state/A.txt、B.txt与after对照
- E:/SH/provenance/audit/dependency_graph.md、N02_legacy_dependency_closure.md
- E:/SH/environments/README.md
- E:/SH/integration/single_spiral_to_hsi/INTERFACE_PLAN.md
- E:/SH/provenance/migration_reports内各烟雾/回归、parity、数值、source_preservation与target_integrity证据
