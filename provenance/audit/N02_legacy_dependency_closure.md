# N02最小旧光学评估闭包

## 决策

采用规划允许的vendor_compat临时子集。安全抽取尚未完成：旧support初始化绑定runtime.old、legacy、p3，且pilot导入model，而N01_2A/model混合了W/C构造与通用测量。贸然裁剪函数会改变动态模块初始化与错误行为。本轮不改写物理函数，复制8个确实被import的旧文件，保留原相对结构，另复制其所需的N00小型src。**函数级去C提炼仍为未完成项**，但独立固定验证已无需旧源或旧结果。

没有复制整个N01目录，没有任何N01旧结果、参数扫描或大批C历史数据。兼容层中未调用的W/C构造仅是文件级封装遗留，不构成C研究分支迁移。

## 文件与实际调用

| vendor_compat中的原相对路径 | 作用/使用函数 |
|---|---|
| experiments/N01_3A_G2_f2_q6_13wave/support.py | phase_free_record，冻结检测封装 |
| experiments/N01_2F_G2_f1_13wave/runtime.py | 模块绑定、add_competition、load |
| experiments/N01_2E_m12_branch_diagnostic/runtime.py | 为analyze提供旧模块与工具绑定 |
| experiments/N01_2E_m12_branch_diagnostic/analyze.py | p3.refine/extract/edges_for/patch_cosine等冻结定位、候选与链接工具 |
| experiments/N01_2E_multiorder_pilot/run.py | lobe_record、sha/write_json/write_csv/save_case的原实现 |
| experiments/N01_2E_multiorder_pilot/model.py | 导入legacy；focus_spiral/a2_height未在迁移验证中调用 |
| experiments/N01_2A/model.py | measure、baseline、locate_peak等通用接口；未调用W/C设计 |
| experiments/N01_1/model.py | asm_memory_bounded、locate_peak、分析纯函数 |

完整来源文件SHA、目标SHA、来源mtime和大小见selected_files.csv/copied_files_sha256.csv。源Git HEAD与dirty/untracked列表见source_git_state/A.txt，文件内容以实际工作树快照为准，不擅自从HEAD还原。改动仅N02 optics的动态模块路径，compat内8文件未改一字节；patch及所有活跃改动见code_adaptations.patch/json。

## parity与独立性证据

source_N02_frozen.json与N02_frozen.json：同一完整冻结高度和mask，546.1nm源场SHA一致、单位入瞳能量一致；complex128小尺寸ASM输出SHA和谱能量统计一致；25波长全部测量记录逐字段完全相同，峰定位/角度/旁峰比/主盘能量误差0；负高度错误处理均为ValueError。

N02_extended.json：重算84行ASM/RS残差、67组对边配对、5项物理峰比；原同一B006边界点q4独立CPU全入瞳求积与旧GPU复场绝对差2.2400628663e-20、相对差1.7067950767e-15。未新增采样点/波长，未启动新优化或16×16诊断。

N02原G2/G3仍FAIL，R仍INCONCLUSIVE。R2原54项输出哈希相同；原55项输入及9项源码均可本地追溯。R2原任务书快照因Windows CRLF与源LF字节不同，已仅恢复LF副本，并与原任务书完整SHA精确相等，记录在supplemental_evidence.csv。路径适配前源码另存source_code_originals，不篡改原manifest。

**支持范围**：新固定输入验证入口在Python审计路径屏蔽下可独立运行；不支持把旧整包审计当作新入口。旧整包审计要求被排除的历史变体与N01结果，仍属于归档限定接口。源码内旧绝对路径出现在历史审计函数时已明确登记，未被静默忽略为通过。
