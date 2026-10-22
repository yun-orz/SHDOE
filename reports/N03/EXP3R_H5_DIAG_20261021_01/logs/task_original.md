# N03-A-EXP3R-H5｜收敛认证失败诊断与候选选择策略审查

> **交付 Codex 的受控科研任务书**  
> 课题：单孔径 DOE、RGB 传感器、9 波段未知亚像素位置—光谱联合恢复  
> 工作根目录：`E:\SH`  
> 任务性质：**诊断优先、旧结果冻结、限定计算预算、不自动放行**  
> 本轮阶段名：`N03-A-EXP3R-H5-DIAG`  
> 预期执行者：Codex；实验完成后由 ChatGPT 经 Engineering Bridge **独立只读审核**。

---

## 0. 一句话目标与执行权限

**查明 EXP3R 的 H5 失败主要来自“缓存最优点与 Powell 成功返回终点不一致”的选择/认证语义，还是来自真实的优化不稳定；量化这种差异对位置与光谱重建的影响。**

本轮主要使用**现有 48 幅 pilot 观测、A/B 结果和优化轨迹**。优先开展无需重新优化的离线分析。只有满足第 6 节条件时，才允许一次 8 例、固定预算的微型补充计算；不运行 504 幅 full，不进入双点、全图像、25 波段或神经网络。

授权修改范围仅限：

1. 新代码：`E:\SH\integration\single_spiral_to_hsi\n03_exp3r_h5_diag\`（如不存在则创建）。
2. 新报告：`E:\SH\reports\N03\EXP3R_H5_DIAG_20261021_01\`。若该目录已经存在，不得覆盖；使用下一可用编号并在报告中说明。
3. 新增针对本轮代码的单元测试（不得改旧测试的通过条件）。

**严禁**修改或覆盖原 EXP3/EXP3R/EXP2/EXP2B 的数据、门禁、源码、日志、图、哈希清单或 DOE 高度；严禁 git add/commit/push；不得触碰 DeepLens RGB 曲线或改变 RGB 权重。冻结的 PSF/DOE 与旧实验的失败门禁必须原样保留。

---

## 1. 背景：本轮应明确区分的事实

以下数字来自上一轮 Bridge 审核，**必须以本地归档原始数据重新核查**，不能直接复制为新实验的结果：

| 对照项目 | A：Powell maxfev=55 | B：Powell maxfev=150 |
|---|---:|---:|
| pilot 数量 | 48 幅观测 | 同一 48 幅观测 |
| clean 最坏定位误差 | 0.011716099996 px | 约 7.345858×10⁻⁷ px |
| Q40 最坏定位误差 | 0.011837610953 px | 约 0.000703469843 px |
| 成功 Powell 起点 | 19/96 | 77/96 |
| 耗尽预算起点 | 77/96 | 19/96 |
| 严格 H5 认证的 B 最终所选结果 | — | **8/48** |
| B 中未获 H5 的选中点 | — | **40/48** |

上一轮 B 组的 40 个未认证选中点被分为：

- **28 个**：来自一个成功收敛起点的中间缓存评价点，但该点**不是成功 Powell 返回终点**。
- **12 个**：只出现于未收敛起点的评价轨迹。

注意：这 **不等于**“有 40 个定位错误的结果”，也 **不等于**“只有 8 个真实局部极小值”。

原 EXP3R 科研门禁：`H2/H3/H4 PASS`、`H5 FAIL`、`decision = EXP3R_PILOT_FAIL`、`full = 0/504 NOT_RUN`。其工程 QA 可以 PASS，但不得将其误写为科研 PASS。上游 `N02 G2`、`N02 G3_Numerics`、`N03 G0` 仍为 **FAIL**；本轮不能更改。

### 1.1 必须先读取的事实来源

请检查下列**真实存在的文件及字段**。不存在、字段结构不符或内容冲突时，记录 `UNVERIFIED` 并暂停相应阶段，**不得自行补造或猜测文件/API**。

- `E:\SH\reports\N03\EXP3R_BUDGET_AB_20261021_01\FINAL_INDEX.md`
- `...\DELIVERY.md`、`...\result_summary.md`、`...\status_semantics.md`
- `...\frozen_contract.json`、`...\pilot_gate.json`、`...\final_qa.json`
- `...\ab_metrics.csv`、`...\optimizer_terminations.csv`、`...\selection_provenance.csv`
- `...\paired_improvement.csv`、`...\archived_A_regression.csv`
- `...\input_manifest.json`、`...\source_manifest.json`、`...\final_delivery_manifest.json`
- `E:\SH\reports\N03\EXP3_UNKNOWN_POS_20261021_02\optimization_traces.json`
- `E:\SH\integration\single_spiral_to_hsi\n03_exp3r\compare_budget.py`
- `E:\SH\integration\single_spiral_to_hsi\n03_exp3r\frozen_pilot.py`
- `E:\SH\integration\single_spiral_to_hsi\n03_exp3\position_solver.py`
- `E:\SH\integration\single_spiral_to_hsi\n03_exp3\forward_adapter.py`

路径中的 `...` 是同一 EXP3R 正式目录的简写。项目文件如有实际差异，优先以 canonical 报告及其 manifest 所指示的真实路径为准，且必须在 `00_preflight.md` 列出差异。

---

## 2. 研究问题、互斥假设与证据标准

### H-A：选择策略与严格 H5 的定义存在错位

当前候选排名可能是在**所有缓存过的位置点**中选取最小残差，而 H5 要求最终点必须与**成功 Powell 起点的返回终点**完全一致。即便某个中间点拟合更好，它也会不满足原 H5。

**支持 H-A 的证据：**大量未认证点来自成功起点的中间评价；与相应成功终点相比，目标值差很小/空间位置很近，并且最终重建性能没有明显下降；在不重新求解的“成功终点限定选择”中，关键指标仍可保持。

**注意：**目标值小不能自动证明优化收敛；位置贴近真值不能倒推当前选择策略在实际测量中可靠。

### H-B：位置搜索确有未充分收敛问题

部分选中位置仅来自预算耗尽轨迹，重新评估或局部精修会继续明显降低残差，或成功终点缺失/空间差异较大。

**支持 H-B 的证据：**终止日志、梯度或邻域下降方向、补充微型精修中残差继续下降、或成功终点策略无法覆盖相应观测。

### H-C：仍有尚未解释的数值与模型不确定性

例如：缓存/终点的浮点坐标精确比较、不同前向计算路径的归一化差异、目标计算不确定、PSF 的 shape-only 位置归一化带来等效性、`SUCCESS` 字段语义混淆等。

所有结论应区分 **observed（直接数据）**、**diagnostic inference（诊断推断）**、**unverified（未证实）**。允许 H-A/H-B 同时对不同案例成立，不必强行只选一个原因。

---

## 3. D0：运行前预检和冻结

在任何新优化计算发生前，完成以下事项：

1. 记录 `git rev-parse HEAD`、`git status --porcelain=v2`、tracked diff 哈希；记录 Python、NumPy、SciPy、PyTorch 版本（仅环境信息），不得改变当前环境。
2. 对 EXP3R 交付 manifest 的输入与产物进行 SHA-256 核对，标出输入 PSF、DOE 高度、mask、RGB 传感器曲线、前向源码的散列；若无法核验，停止。
3. 检查 A/B 是否为相同 48 幅观测与噪声，并确认 B 的唯一主要参数变化为 `maxfev: 55→150`；说明派生总预算 guard `119→309`，不能称为完全独立的优化变量。
4. 核验 A 复现原 EXP3 的 144 行 O/F/J 指标；新报告不得修饰历史失败结果。
5. **逐字保存原 H5 判据**，尤其是“选中缓存点 = 成功 Powell 返回终点”的判断方式、是否要求坐标精确相同、成功状态、NNLS/KKT 约束。校验完整原 gate 为 `EXP3R_PILOT_FAIL`。
6. 预冻结本轮**诊断协议**：数据子集选择规则、可用 trace 字段、新判别阈值（如果使用）、微型计算预算和停止标准。保存 `diagnostic_contract.json`，附 SHA-256 和时间戳。**先冻结再跑任何新的精修**。

新报告 `00_preflight.md` 必须明确：**本轮不会重判 EXP3R 的旧 H5；历史 H5 FAIL 永久保留。**

如果存档中没有逐候选可复现的评价历史，不得假装存在完整轨迹；先列 `trace_availability.json`，明确能分析哪些量，无法分析哪些量。

---

## 4. D1：离线逐例“候选来源—终止状态—目标值”审计（主任务）

**本阶段严格不运行新的位置优化。** 仅读取归档数据并进行一致性复算；允许在内存重算汇总统计，必要的目标值独立复算归入 D2。

### 4.1 每个 B 组 Joint 观测必须生成一条记录

至少包含：

- `observation_id`、`protocol`、`spectrum_id`、`seed`、`position_id`；
- `selected_xy_px`、`selected_objective`、`selected_start_id`；
- `selected_provenance`：`SUCCESSFUL_START_INTERMEDIATE` / `UNSUCCESSFUL_START_ONLY` / `SUCCESSFUL_RETURN_ENDPOINT` / `UNKNOWN`；
- 两个 Powell 起点各自的 `success/status/message/nfev/maxfev`、终点坐标、终点目标值；
- 是否存在**至少一个**成功 Powell 终点，是否存在成功终点与所选缓存点**数值重合**；
- `nnls_call_completed`、最大 KKT 违反量、是否有限值/非负；
- 原始严格 `H5_certified` 与原报告逐行是否一致；
- `position_error_px`、`NRMSE`、`SAM_deg`（这些真值指标仅用于**事后评分**，不得参与候选选择）。

如果原始轨迹没有足够信息明确 `selected_start_id`，必须标 `UNKNOWN`，不得按模型预测补写。

### 4.2 三种不同的“相同”必须分开报告

1. **严格相同**：原 H5 所用的确切比较（保持原样，禁止修改）。
2. **浮点接近**：
   \[
   d_{\mathrm{end}}=\|p_{\mathrm{cache}}-p_{\mathrm{endpoint}}\|_2\quad(\text{detector pixels})
   \]
   单纯作为诊断连续量；若分类使用阈值，必须在新 `diagnostic_contract.json` 预先冻结，不能回填旧 H5。
3. **目标值接近**：
   \[
   \Delta f=f_{\mathrm{endpoint}}-f_{\mathrm{cache}},\qquad
   \Delta f_{\mathrm{rel}}=\frac{\Delta f}{\max(|f_{\mathrm{cache}}|,10^{-12})}.
   \]
   同时报 `f_cache`、`f_endpoint`、绝对差；不可单凭相对差做科研结论。目标公式必须以**源码实际定义**为准，先核验原 `relative_residual` 与优化目标是否平方关系，不能擅自代换。

### 4.3 不允许把“成功起点”误读为“选中解成功”

必须分开汇总：

- 成功/耗尽预算的 **起点数**（B 预期 77/96、19/96）；
- 至少存在一个成功起点的 **观测数**；
- 最终所选缓存点来自成功/失败起点的 **观测数**；
- 原严格 H5 真正认证的 **观测数**（预期 B=8/48）；
- `selected` 恰好为成功终点，但浮点比较可能存在差异的 **观测数**；
- 原先 8/28/12 分组是否精确复现。

所有比例分母明确标记为**起点 96**或**观测 48**，不得混用。

**D1 输出：**`provenance_audit.csv`、`termination_audit.csv`、`h5_exact_replay.json`、`trace_availability.json`、`D1_findings.md`。

---

## 5. D2：不追加优化的“只用成功 Powell 终点”选择反事实

目的：判断 H5 失败中有多大比例属于**选中点身份/来源**的问题，而非缺乏可用的成功终点。此阶段**不能调整原 H5 或光学/NNLS 模型**。

在每个原 B 组观测中，对比：

- **C0（历史基线）**：原 B 的所有缓存点中选残差最小的 `cache-best`，不得重新排序改写。
- **C1（成功终点限定）**：只从原有 Powell `success=True` 的各起点**返回终点**中，按原优化目标选最低的一点；若没有成功终点，写 `NO_CONVERGED_ENDPOINT`，不得回退为 C0 并称之为成功。

**C1 只是离线反事实，不是新的实验成功证明。** 如果归档只保存了不足以重构终点的轨迹，允许使用**冻结前向与 NNLS**重新评价这些确定终点；此时需记录完整代码/计数/输入哈希，不能声称“完全只读重算”。绝不能借真值选择 C1。

逐观测汇总：

- C0、C1 的 x/y、目标值、光谱解（能可靠重算时）、位置误差/NRMSE/SAM（只在选完 C1 后评分）。
- `objective_regret = f(C1)-f(C0)`；不能因同一目标本身有不同比例尺度就直接跨谱汇总未归一化目标值。
- `position_shift = ||p(C1)-p(C0)||`，误差变化和 SAM 变化。
- 存在成功终点与不存在成功终点的子组差异，clean 与 Q40 分开。
- 重新汇总 C1 的 `NRMSE≤0.01` 比例、clean 最大定位误差、Q40 最大定位误差，**仅作探索性的独立评估**；不因此自动通过 H5/H2/H3。
- 检查选中点在 ±0.5 px 搜索边界附近的行为以及是否存在多重局部极小值的可见证据；不能由局部采样推断全域唯一性。

新增科学解释约束：如果 C1 的有效覆盖率低，说明“限制返回终点”不是可行的完整替代策略；如果 C1 覆盖高但重建变差，则严格 H5 与当前最小残差选点目标之间存在实质折中，而非简单编码 Bug。

**D2 输出：**`endpoint_only_comparison.csv`、`D2_summary.md`、`D2_decision.json`。若 D2 所需的数据不足，必须 `D2_NOT_VERIFIABLE` 而非补造。

---

## 6. D3：必要时的一次性微型局部精修（有条件，可跳过）

**触发条件：**完成 D1/D2 后，仍无法分辨主要案例的失败原因，且冻结前向与保存的观测 `y` 能重新获取，才允许 D3。否则报告 `D3_SKIPPED` 并直接交付。

### 6.1 取样和预算

- 仅从**原 B 的 48 个已存在观测**中确定 8 例，固定选样规则并在 `diagnostic_contract.json` 保存所选 ID 后运行。
- 建议按原 `selected_provenance` 分类：成功终点类 2 例、成功起点中间点类 3 例、未收敛起点类 3 例。每类按 observation_id 的稳定字典序挑选，不依据真位置或真谱选择；某类不足则全取并按另一类的固定顺序补满，事先记录。
- 只运行**一种**微型方法：以 B 的历史 `cache-best` 作为新起点，在原 ±0.5 px 边界内执行**一次**有界 Powell 局部精修，`maxfev=80`、`xtol/ftol` 和目标函数等参数保持原样。
- 最多 **8 个新 Powell 起点，总计最多 640 次新函数评价预算**（不包括必要的目标值复核；所有实际求解次数必须记录）。不能把这轮称为与 A/B 等算力的比较。
- 不增新初值、不临时改预算、不循环追加候选、不调用真值辅助搜索；如内存、运行时间或输入校验失败，直接停止。

### 6.2 微型实验的有效比较

报告每一例新精修的 `success/status/message/nfev`、起终点、目标值下降与否、定位误差、NRMSE、SAM、KKT、边界情况；保留 C0/C1/新精修三列。不得把从同一噪声观测重新优化所得的指标描述为独立测试泛化性能。

D3 即使 8/8 成功，也**只允许宣布“8 例内存在可修复证据”**；不得直接解锁旧 H5 或 504 full。若失败也按原样保留，不再追加其他优化器。

**D3 输出：**`micro_polish_cases.csv`、`D3_summary.md`、`D3_status.json`；未执行则写明 `SKIPPED` 原因。

---

## 7. 验收机制与停止判定

### 7.1 工程 QA（应可独立判定）

至少包括：

- 输入 manifest 全部匹配；历史目录未被修改；`git HEAD/tracked diff` 前后不变。
- 原 48 幅 B 观测、96 起点、8/28/12 分类的统计可复现；如真实归档与此前审核不同，明示差异，不得为了 PASS 修改数据。
- 原严格 H5 的认证数和门禁状态被**原样回放**；实际 `EXP3R_PILOT_FAIL` 不被覆盖。
- 离线候选排序完全不使用 `dx_true/dy_true`、`truth`、`NRMSE` 或 `SAM`；仅以 `y`、估计目标和已冻结模型计算。
- 分组比例均使用正确的 48/96 分母；C1 在无成功终点时明确为 `NO_CONVERGED_ENDPOINT`。
- D3 未触发时不能生成伪造的微型结果；触发后新评价预算必须有上界与可核查日志。
- 报告中将 `nnls_returned`、`NNLS_KKT_pass`、`powell_success`、`strict_H5_certified`、`new_diagnostic_label` 五种状态分列，不互相代替。
- 输出自动核验 JSON、源码快照、运行命令、冻结配置、随机数种子和结果 hash。

### 7.2 本轮科研决策（不是原 H5 的重定义）

仅允许以下结果之一：

1. `H5_DIAG_SELECTION_SEMANTICS_DOMINANT`：有足够逐例来源、目标值与成功终点对照，表明**多数**未认证案例源于缓存点/终点选择语义；对于仍无法解释的案例，逐例列出，不得称全部解决。
2. `H5_DIAG_CONVERGENCE_LIMITED`：有明确轨迹与定量证据显示优化未充分收敛、可进一步下降或成功终点不足；给出其观测占比。
3. `H5_DIAG_MIXED`：不同子集机制不同。
4. `H5_DIAG_INCONCLUSIVE`：输入、轨迹或因果证据不足，不能作判断。

以上标签**必须附有逐例证据和至少两项量化指标**；可支持混合机制，禁止因“一次增加预算提升定位精度”而直接断言全体情况均是预算不足。

### 7.3 强制停止

遇到以下任意情况立即停止相应实验，不做参数试错：

- 输入哈希与冻结基线不一致；历史文件变化；来源记录无法追踪，未解决不进行 D3；
- 真值被传给 C1 或 D3 优化选择；
- 前向、PSF、RGB 曲线、NNLS、目标函数发生非预注册的修改；
- D3 的 8 例和 80 次评价上限已经用完，无论 PASS/FAIL 都停止；
- 无法一致复现旧 H5 时，停止并提交 `INCONCLUSIVE`，不得绕过复核；
- 研究门仍 FAIL 时不得自行执行 full / 双点。

**原 EXP3R `H5 FAIL`、`full NOT_RUN` 和上游 `N02/N03 FAIL` 在本轮始终保持原状。**

---

## 8. 必须交付的文件

在一个全新 canonical 目录中保存：

```text
E:\SH\reports\N03\EXP3R_H5_DIAG_20261021_01\
├── DELIVERY.md                     # 入口：一句科研决策、实际执行范围和全部证据路径
├── 00_preflight.md                 # 原门状态、git/哈希、源码/文件存在性核对
├── diagnostic_contract.json       # 实验开始前冻结；包括D3取样与预算规则
├── trace_availability.json         # 归档轨迹究竟有多少信息
├── provenance_audit.csv            # B的48例逐例来源与H5回放
├── termination_audit.csv           # 96个B Powell起点及终止/预算
├── h5_exact_replay.json            # H5原规则原结果逐项对照
├── D1_findings.md
├── endpoint_only_comparison.csv    # C0和C1反事实；可能存在无成功终点
├── D2_summary.md
├── D2_decision.json
├── micro_polish_cases.csv          # 仅当D3真的执行；否则不创建
├── D3_summary.md                   # 执行或SKIPPED及原因
├── D3_status.json
├── diagnostic_decision.json        # 四种结论之一、证据、限制和停止动作
├── results_summary.md             # 含按clean/Q40分组的统计表和最差案例
├── tests.json
├── postrun_checks.json
├── input_manifest.json
├── source_manifest.json
├── final_manifest.json
└── logs/
    ├── run_commands.md
    ├── events.jsonl
    ├── source_snapshot/
    └── run_record.json
```

需要时可以附 D1/D2 差异直方图与按 provenance 分组散点图，但**图不替代 CSV/JSON 原始数据**。如果原实验档案缺失关键字段，允许删减无法计算的数值输出，但必须在 `trace_availability.json`、`DELIVERY.md` 和 `diagnostic_decision.json` 声明原因，不能伪造完整交付。

### `DELIVERY.md` 最小模板

必须包含：

- 旧实验结果冻结核验：EXP3R `H2/H3/H4 PASS / H5 FAIL / full 0/504`。
- 本轮实际完成 `D0/D1/D2/D3` 的状态；有无新优化、多少次。
- B 的 48 例 H5 来源分类与精确回放。
- C1 是否存在有效成功终点，C0/C1 差异与失败来源。
- 是否发现真实目标值可继续下降的直接证据。
- 原失败与新诊断标签分离，N02/N03 上游 FAIL 不变。
- 仅一个**有条件的下一步建议**：若选择语义为主，另立并预注册新的“返回终点/两阶段精修策略”pilot；若未收敛为主，做目标函数和求解器机制分析；如证据不足，暂停推进。

---

## 9. 推荐单元测试

请至少涵盖：

1. **无 GT 泄漏**：C1/D3 接口禁止接收真位置、真谱和真值误差；用带陷阱值的仿真对象确认不会访问 GT 字段。
2. **缓存/终点分类**：构造 success 中间点、success 返回点、failure-only、无成功终点四种最小轨迹，分类准确。
3. **精确匹配 vs 接近匹配**：两个浮点位置仅有极小偏差时，严格 H5 仍按原规则失败；新诊断可报告距离而不偷偷改 H5。
4. **同一函数目标值复现**：用冻结前向回算选择点与终点，NNLS 对应矩阵相同；KKT/有限值/非负检查明确。
5. **缺失轨迹字段**：严格标 `UNVERIFIED`，禁止填充虚构终点。
6. **不得覆盖旧门**：读取旧 `pilot_gate.json` 前后哈希不变；新标签从不覆写旧门。
7. **微型预算强制限制**：不超过 8 个例、每例 1 个新起点、每起点 maxfev 80；未触发时零新求解。
8. **完整路径与日志**：现有报告写入范围之外的写操作被拒绝；输入/源码/交付哈希可核验。

所有测试遵循“先失败样例、再实现、再验收”的逻辑；不得仅测试 JSON/CSV 字段是否存在而不测实际来源分类、比较和限额。

---

## 10. Codex 的执行顺序与停机报告

**严格顺序：**

`查看旧档案 → D0哈希/门预检 → 冻结新诊断协议 → D1轨迹来源 → D2成功终点反事实 → 判断是否必要 D3 → （最多一次D3） → 单元测试及一致性检查 → 交付 → STOP`

中间任何一步不能直接扩展为“优化下一种算法”“全量 504”“双点场景”。若发现原始实验存在代码缺陷，只在本轮报告中列示和最小隔离验证，不得就地修改 EXP3/EXP3R 原文件；确实需要修复时，应明确提出另立实验。

请最终只向用户汇报：

1. canonical 输出路径；
2. D1/D2/D3 的实际运行情况；
3. 四种科研诊断标签之一及最多三个关键定量证据；
4. 旧 H5 与上游 N02/N03 门有没有变化（正确答案应为**没有**）；
5. 原始指标和新诊断是否足以支持进一步单点求解器改进；
6. 全程是否触碰旧文件、是否提交 Git（预期均否）。

> **科研边界提醒**：本阶段研究的是固定 9 波段单孔径、已知粗中心、shape-only 多波长 PSF 的**合成观测内**优化收敛与候选选择。即使 H5 机制被解释清楚，也不能据此宣称 N02 数值可信门已通过、真实相机精度满足要求、双点可分辨，或获得整幅高光谱成像能力。
