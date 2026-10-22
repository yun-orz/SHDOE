from pathlib import Path
import json,csv,os,hashlib,collections
R=Path('E:/SH');N=R/'optics/n02_single_spiral';F=R/'optics/n00_forward';D=R/'framework/DeepLensHSI'
def create(rel,s):
 p=R/rel;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
create('README.md',r'''# SH：单孔径 DOE 与高光谱研发工作区

迁移日期：2026-10-20。迁移验收结论：**PASS_WITH_KNOWN_LIMITATIONS**。本目录保留当前工作树快照，不包含旧仓库的 `.git`，未建立新Git仓库，未自动push。

## 实测结果与科研状态

| 模块 | 本次独立验收 | 数值对照 |
|---|---|---|
| N00 多波长前向 | T01–T06 PASS | 31×512×512；与冻结参考PSF、原始强度最大差均为0 |
| DeepLensHSI 原相机与预训练网络 | 8场景重新编码、推理及评价 PASS | 平均PSNR 18.186638236 dB、SSIM 0.662075、SAM 39.223211288°；与旧R05逐场景张量和指标完全一致 |
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

DeepLens本次真实执行的是子目录中的`5_eval_pretrained.py --limit 8`和`6_evaluate_metrics.py`，源码未修改；默认输出固定为`results/R05_validation`。该位置已有本次结果，**不要直接重复执行并覆盖**。原脚本暂未提供自定义输出参数，未来新增推理轮次应先增加输出目录参数并拒绝覆盖；当前可独立检查`results/R05_validation/metrics.csv`及已有日志。

完整命令、耗时及退出码见`provenance/migration_reports/*_command.json`；报告见`provenance/migration_reports/final_report.md`。

## 已知边界

旧N02/R的整包审计会要求所有历史变体与N01历史结果，本次精简后不支持重跑该历史审计。R2旧命令行校验器仍按旧绝对路径和原源码哈希工作，改用本工作区的固定输入入口及`R2_input_resolution.json`映射。历史文档、manifest内的旧路径保留原文用于溯源，不能机械地全替换。

`n00_forward/scripts/snapshot_reference.py`已显式停用；旧`build_report.py`是依赖旧双输出目录布局的历史工具，本次不重跑。新的迁移报告独立生成。训练集、其他光学模型及训练复现不在本次范围。
''')
create('environments/README.md',r'''# 运行环境与移植说明

本次实测环境为D:/MiniAnaconda/envs/deeplens_hsi_4060/python.exe：Python 3.10.22、PyTorch 2.5.1+cu121、torchvision 0.20.1+cu121、NumPy 2.2.6、SciPy 1.15.3、CUDA运行时12.1，GPU为NVIDIA GeForce RTX 4060 Laptop GPU。与历史R05和N02环境一致。N00也在该环境通过T01–T06，与旧PSF完全一致。

系统默认python为3.10.4，未将其当成验收环境。doe_research实查为Python 3.12.15 / torch 2.10.0+cu128，未用于本次验收。原DeepLens environment.yml保留原文，其CUDA12.8规格不代表历史R05或本次环境。

`runtime_versions.json`记录完整实测包版本；`requirements_runtime.txt`依据已安装distribution的实际版本生成，包含PyTorch cu121索引。该清单不含`file:///home/conda`依赖。原N00 requirements.txt保留来源原文；其中不可移植的packaging路径，在新清单中由实际安装的packaging版本替代，没有删除依赖或盲装新版。

可移植环境安装示例（本次未新建或重装环境，不能宣称异机安装已验证）：

```powershell
conda create -n sh_hsi python=3.10.22
conda run -n sh_hsi python -m pip install -r E:\SH\environments\requirements_runtime.txt
```

驱动、CUDA兼容性与包索引可用性需在新主机重新核验。完整科研依赖未包含在Python wheel清单中的系统库，不应与二进制环境镜像等同。

验收通过`provenance/tools/record_run.py`记录命令、工作目录、退出码和耗时，并设置PYTHONDONTWRITEBYTECODE、MPLCONFIGDIR、TORCH_HOME、TEMP/TMP指向SH子目录。`provenance/guard/sitecustomize.py`拒绝访问两个源工程及个人Downloads；N00的测试子进程也通过PYTHONPATH继承该屏蔽。`source_N02_parity`只读源侧比较特意不启用屏蔽。

少量Matplotlib字体缓存和运行临时目录保留在provenance/runtime_cache；这是本次验收生成的小型缓存，不是迁入的旧缓存。不执行未经许可的删除操作。
''')
create('integration/single_spiral_to_hsi/INTERFACE_PLAN.md',r'''# 单孔径PSF → 编码 → 重建接口计划（尚未实现）

## 已有接口与差异

N00正式PSF为`[31,512,512]`，400–700nm、10nm步长；N00只是解析参考几何验收，不是N02器件的替代物。
N02 B2标准为420–660nm的25波长，另有546.1nm及蓝端诊断采样。单波长NPZ包含`raw_roi`、`normalized_psf`、`coords_um`、`record_json`；横向坐标为`(index-(N-1)/2)*pitch`，高度/横向单位um，传播距离mm，波长nm。标准ROI宽512um、原生pitch 1um；收敛试验含0.5um网格。
DeepLens当前CaveDataset产出`img[B,31,H,W]`和`wvln[B,31]`（um，0.4–0.7），验证H=W=512；HSICamera.render返回编码RGB `[B,3,H,W]`与原始谱GT `[B,31,H,W]`。NAFNet输入3通道、输出31通道。原HSICamera自行计算31个PSF（默认ks=201）并调用render_psf，不接受N02 NPZ。

## 拟定PSF数据契约

未来适配器输出强度核`P[K,Ny,Nx]`、严格递增波长`lambda_nm[K]`、物理坐标与像元间距、各通道入瞳功率及ROI捕获份额。保留raw强度和裁剪归一化两种表示：raw在入瞳1的基准下以um^-2计，乘dx*dy积分；normalized_psf为ROI内概率质量，总和1。不能用逐ROI归一化抹掉随波长变化的能量损失。

x向右、y随数组行号增加，并以origin=lower显示；偶数网格轴心在像元之间。适配需明确核的物理中心、半像元偏移、fftshift规则，避免将波长相关离轴峰自动居中消除光谱编码。记录设备、复数精度、材料假设、固定高度与mask完整SHA。

N02波段不覆盖DeepLens 400–700nm；需先选择经过物理验收的完整采样，或重新定义波段与重建网络。不能简单外推缺失端点后称为31通道复现。原31通道权重对新光学系统的适用性尚未验证。

## 重采样、卷积与传感器

从光学um网格到探测像元时，按实际传感器pitch、放大率及填充率做面积积分；先抗混叠再降采样，检查总能量及质心。不能直接resize图像代替能量守恒重采样。原传感器JSON与lens sensor_res/sensor_size需显式对齐，图像512像素与传感器全分辨率不应混为一谈。

场景编码应明确是线性强度卷积还是库函数的互相关，核翻转必须可追溯。为避免循环卷积，选定零填充/实际场外模型与valid或same裁剪，预注册边界宽度并以delta场景与恒定场景检验；禁止无说明使用周期场景。先验证相干传播所得PSF与非相干空间卷积假设的适用范围，包括视场和平移不变性。

谱混合形式暂定`Y_c=Σ_k R_ck*Δlambda_k*(P_k * X_k)`；若R或输入已包含谱带积分，则不能重复乘Δlambda。必须匹配原RGBSensor.response_curve的采样、单位与幅度标定。原基线render中传感器噪声调用被注释；新接口需分别定义无噪声验证与经过标定的噪声模型，不擅自混用。

## 前后向一致性与验收

未来才实现输入适配、PSF编码器与网络接入。先做delta定位/能量守恒、颜色响应、边界样本及前向/伴随内积一致性；仅在需要优化时验证梯度。固定PSF不可在反传时隐式重设计或按波长包裹高度。

重建输入为明确标定的RGB或新测量张量，输出定义到同一波长序列、空间网格及辐射尺度。评价分别给出PSNR、与原库一致的SSIM、SAM有效像素规则，并记录训练/验证划分。新相机模型下的原权重先作为迁移基线，不能预称端到端成功。

当前先决条件：N02 G2/G3仍FAIL、R为INCONCLUSIVE、R2全局结论未定，G4–G8未测试。以上设计文档没有授予物理门通过，也没有执行新的RS16×16或DOE优化。
''')
create('provenance/audit/dependency_graph.md',r'''# 真实依赖图与文件闭包

源码逐行AST导入/动态载入/读盘调用共730项，详见dependency_graph_details.json；源绝对路径扫描见absolute_paths_scan.json。R2全部55项输入逐个本地解析并对完整SHA，见R2_input_resolution.json；其9项源码另见R2_source_resolution.json。

```mermaid
flowchart TD
  R2[r2_run / r2_common] --> R[p0b_common]
  R --> O[n02 optics]
  O --> S[vendor support]
  S --> F[N01_2F runtime]
  S --> P[N01_2E diagnostic runtime / analyze]
  F --> U[N01_2E pilot run / model]
  P --> U
  U --> A[N01_2A model]
  A --> B[N01_1 model]
  A --> C[N00 phase / propagation]
  O --> C
  R2 --> H[B2 height / mask / config]
  R2 --> Q[R / R2 original raw arrays and protocols]
  O --> T[PSF cases / frozen G2 G3 gates]
```

DeepLens路径闭包：5_eval_pretrained → hsi_dataset/CaveDataset → cave_val.txt中8场景PNG；HSICamera → diffractive lens与原planar_doe.npy、RGBSensor传感器JSON；NAFNet → nafnet_hsi.pth；6_evaluate_metrics → 新生成的8个spectra.pt → 原src.utils.batch_ssim。完整src保留内部相对import，训练数据未复制。

N00：tests与run_n00_psf → src/spiral_hsi/optics；baseline YAML驱动31波长，正式输出只写新目录。原git HEAD查询改为source_snapshot.json，不依赖旧.git。

B2闭包保留：标准420–660nm每10nm、420–430nm每1nm、546.1nm；所有冻结convergence/cases（包括complex64、cpu_asm、dx05、Fresnel、pad4）；B2高度、mask、冻结hash、各类指标/Gram、根目录协议与门控。未选入B0/B1/B3、制造扰动及大批扫描。R和R2诊断整体保留，历史来源清单可能引用未选入的其他变体，不能据此重跑整包历史审计。

路径分类：历史报告和manifest的旧绝对路径保留原文；活跃N02支持模块和任务书指向新目录。N02原audit.py中的N01追溯数据、个人规划书是历史审计入口限定依赖，未纳入新固定输入验证的运行闭包；若调用该旧audit函数，应预期明确失败，不得调用后声称独立全量重演。N00旧build_report依赖旧双输出布局，未运行；snapshot_reference已显式禁用。

独立性验证：路径屏蔽启用时N00子进程、N02三入口导入、固定数值验证、DeepLens8场景推理和指标均完成。源侧parity为唯一刻意读取旧源码的数值对照，不算独立运行证据。路径屏蔽自测成功拒绝两个源README的读取。
''')
create('provenance/audit/N02_legacy_dependency_closure.md',r'''# N02最小旧光学评估闭包

## 决策

采用规划允许的vendor_compat临时子集。安全抽取尚未完成：旧support初始化绑定runtime.old、legacy、p3，且pilot导入model，而N01_2A/model混合了W/C构造与通用测量。贸然裁剪函数会改变动态模块初始化与错误行为。本轮不改写物理函数，复制8个确实被import的旧文件，保留原相对结构，另复制其所需的N00小型src。**函数级去C提炼仍为未完成项**，但独立固定验证已无需旧源或旧结果。

没有复制整个N01目录，没有任何N01旧结果、参数扫描或大批C历史数据。兼容层中未调用的W/C构造仅是文件级封装遗留，不构成C研究分支迁移。

## 文件与实际调用

| vendor_compat中的原相对路径 | 作用/使用函数 |
|---|---|
| experiments/N01_3A_G2_f2_q6_13wave/support.py | phase_free_record，冻结检测封装 |
| experiments/N01_2F_G2_f1_13wave/runtime.py | 模块绑定、add_competition、load |
| experiments/N01_2E_m12_branch_diagnostic/runtime.py | 为analyze提供旧模块与工具绑定 |
| experiments/N01_2E_m12_branch_diagnostic/analyze.py | p3.refine/extract/link等冻结定位、候选与链接工具 |
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
''')
create('framework/DeepLensHSI/MIGRATION.md',r'''# 本工作树迁移说明

这是2026-10-20对源B当前工作树的精选快照，保留未提交修改的实际字节；原Git不在此目录。原README署名与CC BY-NC 4.0声明保持原文。

仅含8个CAVE验证场景、nafnet_hsi预训练参数和原光学/传感器输入；训练集和额外光学示例未纳入。README中assets/video1_raw.gif等展示媒体及训练入口的非验证资源不在本次范围。

reference_results/R05_validation是旧R05原始参考；results/R05_validation是本次重新编码、推理与评价的新结果。8场景GT、pred和指标均与历史参考完全一致。原5/6脚本未改，固定输出位置已有结果，不应直接复跑覆盖；后续应先增加新输出目录参数。

环境、实测命令及最终限制见E:/SH/environments/README.md与E:/SH/provenance/migration_reports/final_report.md。
''')
# 盘点原N00两份参考的文件SHA差异，不重新读取原目录。
inv=json.loads((R/'provenance/manifests/source_A_inventory.json').read_text(encoding='utf-8'));by={r['relative']:r for r in inv}
x={k.removeprefix('results/N00/'):v for k,v in by.items() if k.startswith('results/N00/')};y={k.removeprefix('results/N00_verified/'):v for k,v in by.items() if k.startswith('results/N00_verified/')}
comparison=dict(PSF_cube_sha_equal=x['psf_cube.npz']['sha256']==y['psf_cube.npz']['sha256'],common_files=len(x.keys()&y.keys()),different_sha_files=[k for k in x.keys()&y.keys() if x[k]['sha256']!=y[k]['sha256']],only_N00=sorted(x.keys()-y.keys()),only_verified=sorted(y.keys()-x.keys()),decision='仅复制N00_verified；psf_cube原始文件SHA完全相同；运行耗时/环境报告差异原位保留')
create('provenance/audit/N00_reference_deduplication.json',json.dumps(comparison,ensure_ascii=False,indent=2))
print('README, environment, interface, dependency/closure audit written')
