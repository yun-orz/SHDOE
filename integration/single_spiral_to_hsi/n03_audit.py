"""N03-0只读审计：只新增审计产物，不运行传播、优化或重建。"""
import argparse
import ast
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import scipy
import torch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True, help='必须是尚不存在的目录')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError(f'拒绝覆盖：{out}')
    start = time.perf_counter()
    def git(*parts):
        return subprocess.check_output(['git', '-C', str(root), *parts], encoding='utf-8').strip()
    initial_git = dict(root=git('rev-parse', '--show-toplevel'), branch=git('branch', '--show-current'),
                       head=git('rev-parse', 'HEAD'), dirty=git('status', '--short', '--untracked-files=all'))
    base = root / 'optics/n02_single_spiral'
    old = base / 'results/n02/n02_20261019_02'
    b2 = old / 'B2'
    r2 = base / 'results/n02_1c_r2/n02_1cr2_20261020_02'
    sensor_path = root / 'framework/DeepLensHSI/sensors/flir/BFS-U3-200S7C-C.json'
    sensor_code = root / 'framework/DeepLensHSI/src/sensor/sensor.py'
    inputs = [b2 / 'height_um.npy', b2 / 'aperture_mask.npy', b2 / 'height_metadata.json',
              b2 / 'frozen_sha256.json', b2 / 'config.json', b2 / 'standard_metrics.csv', old / 'gates.json',
              sensor_path, sensor_code, root / 'framework/DeepLensHSI/hsi_dataset.py',
              root / 'framework/DeepLensHSI/src/hsi_camera.py', root / 'framework/DeepLensHSI/src/deeplens/render_psf.py',
              root / 'framework/DeepLensHSI/5_eval_pretrained.py',
              root / 'framework/DeepLensHSI/configs/1_deeplens_hsi.yml',
              root / 'framework/DeepLensHSI/datasets/cave_val.txt',
              root / 'integration/single_spiral_to_hsi/INTERFACE_PLAN.md', root / 'README.md',
              base / 'reports/n02_1c_r/n02_1cr_20261020_01/summary_v2.md',
              base / 'reports/n02_1c_r2/n02_1cr2_20261020_02/N02_1CR2_final_audit.md',
              base / 'reports/n02_1c_r2/n02_1cr2_20261020_02/N02_1CR2_next_step_decision.md',
              r2 / 'manifest.json', r2 / 'artifact_manifest.json', r2 / 'input_hashes.json',
              r2 / 'decision.json', root / 'provenance/migration_reports/N02_frozen.json', Path(__file__).resolve()]
    inputs += sorted((base / 'experiments/n02').glob('*.py'))
    inputs += sorted((base / 'src/spiral_hsi/optics').glob('*.py'))
    inputs += sorted((base / 'experiments/n02_1c_r2').glob('*.py'))
    cases = sorted((b2 / 'cases').glob('*.npz'), key=lambda p: float(p.stem[:-2]))
    inputs += cases
    checks = []
    def check(name, passed, detail=None):
        checks.append(dict(name=name, passed=bool(passed), detail=detail))
    frozen = json.loads((b2 / 'frozen_sha256.json').read_text(encoding='utf-8'))
    missing_frozen = []
    for name, digest in frozen.items():
        if (b2 / name).is_file():
            check('冻结文件哈希:' + name, sha(b2 / name) == digest)
        else:
            # 精选迁移没有保留全体历史诊断文件，明确记录缺项，不伪造全包通过。
            missing_frozen.append(name)
    rows = []
    for path in cases:
        with np.load(path, allow_pickle=False) as z:
            raw, norm, coord = z['raw_roi'], z['normalized_psf'], z['coords_um']
            rec = json.loads(z['record_json'].item())
            check('PSF数组:' + path.name, raw.shape == (512, 512) and norm.shape == raw.shape
                  and np.isfinite(raw).all() and np.isfinite(norm).all() and raw.min() >= 0
                  and np.allclose(coord, np.arange(512) - 255.5, atol=1e-12, rtol=0))
            err = float(np.max(np.abs(norm - raw / raw.sum())))
            check('归一化:' + path.name, err < 1e-15 and abs(raw.sum() - rec['crop_energy']) < 1e-12)
            rows.append(dict(path=str(path.relative_to(root)), wavelength_nm=rec['wavelength_nm'],
                             shape=list(raw.shape), dtype=str(raw.dtype), pitch_um=rec['pitch_um'],
                             raw_sum=float(raw.sum()), normalized_sum=float(norm.sum()),
                             normalization_max_error=err, crop_fraction=rec['crop_fraction'],
                             edge_fraction=rec['edge_fraction'], peak_x_um=rec['peak_x_um'],
                             peak_y_um=rec['peak_y_um'], status=rec['n02_status'],
                             height_array_sha256=rec['height_array_sha256']))
    with (b2 / 'standard_metrics.csv').open(encoding='utf-8-sig') as f:
        native = [float(row['wavelength_nm']) for row in csv.DictReader(f)]
    sensor = json.loads(sensor_path.read_text(encoding='utf-8'))
    wavelengths = np.array(sensor['wavelengths']) * 1000
    response = np.array([sensor[c + '_response'] for c in ['red', 'green', 'blue']])
    check('RGB响应覆盖与非负', response.shape == (3, 31) and np.isfinite(response).all()
          and response.min() >= 0 and min(native) >= wavelengths.min() and max(native) <= wavelengths.max())
    # 提取原类中的纯响应函数，避开ISP初始化；执行的是原函数源码，不是改写公式。
    tree = ast.parse(sensor_code.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RGBSensor')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'response_curve')
    env = {'torch': torch}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(sensor_code), 'exec'), env)
    probe = SimpleNamespace(wavelengths=[0.45, 0.65], red_response=torch.tensor([0., 1.]),
                            green_response=torch.tensor([0., 0.]), blue_response=torch.tensor([1., 0.]))
    actual = env['response_curve'](probe, torch.tensor([[[[2.]], [[7.]]]]))
    check('原响应函数RGB顺序toy', torch.equal(actual.flatten(), torch.tensor([7., 0., 2.])), actual.flatten().tolist())
    datasets = []
    framework = root / 'framework/DeepLensHSI'
    for line in (framework / 'datasets/cave_val.txt').read_text().splitlines():
        folder = (framework / line.strip()).resolve()
        pngs = sorted(folder.glob('*.png'))
        stats = []
        for p in pngs:
            inputs.append(p)
            im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            legacy = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            stats.append(dict(path=str(p.relative_to(root)), shape=list(im.shape), dtype=str(im.dtype),
                              min=int(im.min()), max=int(im.max()), legacy_max=int(legacy.max())))
        check('CAVE文件数量:' + folder.name, len(pngs) == 31)
        datasets.append(dict(path=str(folder), bands=stats))
    snapshots = {str(p.relative_to(root)): dict(sha256=sha(p), bytes=p.stat().st_size) for p in dict.fromkeys(inputs)}
    gates = json.loads((old / 'gates.json').read_text(encoding='utf-8'))
    check('保留G2/G3失败事实', gates['G2']['status'] == gates['G3_Numerics']['status'] == 'FAIL')
    # 独立重新核对最新R2全部封存产物，只读回查，不运行求积。
    r2_manifest = json.loads((r2 / 'artifact_manifest.json').read_text(encoding='utf-8'))
    for name, digest in r2_manifest.items():
        p = r2 / name
        check('R2产物哈希:' + name, sha(p) == digest)
        snapshots[str(p.relative_to(root))] = dict(sha256=sha(p), bytes=p.stat().st_size)
    preservation = all(sha(root / p) == data['sha256'] for p, data in snapshots.items())
    check('审计输入前后哈希不变', preservation)
    standard = [r for r in rows if r['wavelength_nm'] in native]
    manifest = dict(stage='N03-0', decision='G0_FAIL_STOP',
                    timestamp=datetime.now(timezone(timedelta(hours=8))).isoformat(), git=initial_git,
                    environment=dict(python=sys.version, executable=sys.executable, numpy=np.__version__,
                                     scipy=scipy.__version__, torch=torch.__version__, opencv=cv2.__version__,
                                     platform=platform.platform(), audit_device='CPU',
                                     cuda_available=torch.cuda.is_available(),
                                     gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None),
                    optical_config=json.loads((b2 / 'config.json').read_text()),
                    native_standard_wavelengths_nm=native, archived_psf_cases=rows,
                    psf_convention=dict(axis='每个文件H,W；波长由文件及record_json共同给出',
                                        raw_unit='um^-2 / 单位入瞳功率', normalized_unit='ROI内概率质量',
                                        roi_um=512, pitch_um=1, coords_um=[-255.5, 255.5],
                                        boundary='4096×4096周期ASM传播，居中裁512×512',
                                        source_grid=[2048, 2048], source_padding=2),
                    sensor=dict(path=str(sensor_path), wavelengths_nm=wavelengths.tolist(),
                                channel_order=['R', 'G', 'B'], raw_relative_response=response.tolist(),
                                existing_scale='全部三通道共同除以31点green_response之和',
                                green_reference_sum=float(response[1].sum()),
                                interpolation='旧接口无插值且不按输入波长匹配；只按谱轴索引求和',
                                integration='旧代码无显式Delta-lambda；相对离散权重，绝对响应单位未标定',
                                pixel_pitch_um=12340/4504),
                    datasets=datasets, historical_gates=gates, checks=checks, inputs=snapshots,
                    historical_frozen_manifest_missing_files=missing_frozen,
                    elapsed_seconds=time.perf_counter()-start)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'logs').mkdir()
    with (out / '00_manifest.json').open('x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    lo, hi = min(r['crop_fraction'] for r in standard), max(r['crop_fraction'] for r in standard)
    audit = f'''# N03-0 现状审计

判定：**G0 FAIL，按任务书停止；N03-A未执行**。可定位并溯源最新完整B2候选，但尚不能确认为数值可信的全波段单螺旋PSF。不是断言该DOE不含光谱信息，也没有运行重建后判负。

## 1. 仓库与来源

根目录 `{root}`，分支 `{initial_git['branch']}`，HEAD `{initial_git['head']}`。用户交接时git status为空；脚本起跑状态见manifest（包含本轮新增审计脚本）。无迁移、无删除、无原模块修改。

最新完整多波长候选为 `{b2}`；生成入口 `experiments/n02/run.py`，传播实现 `experiments/n02/optics.py`。不是N00解析参考、W/C型、双螺旋，也不是R2的局部选点数组。R/R2继续使用同一冻结高度，没有发布新的全ROI全波段合格PSF。
高度SHA-256 `{sha(b2 / 'height_um.npy')}`；mask SHA-256 `{sha(b2 / 'aperture_mask.npy')}`。所有逐波长数组、生成源码、元数据、原报告及校验哈希见00_manifest.json。原文件哈希与数组字节哈希不同，分别保留，未混用。

## 2. 维度、波长与物理约定

标准原生波长共{len(native)}个：`{native}` nm；额外546.1nm设计波长和蓝端诊断数组亦逐项盘点，总计{len(rows)}份，未插值生成PSF。配置的L=8是设计环带参数，不是光谱通道数。
数组键raw_roi/normalized_psf均512×512 float64，coords_um为512点[-255.5,255.5]，pitch=1um，偶数网格轴心在像元之间。x向右，y随行号增大、绘图origin=lower。PSF真实峰位保留，未配准。
孔径直径1000um；物距180mm，像面22.495mm，设计焦距20mm；源网格2048²、padding=2，ASM周期域4096²后居中裁512um ROI。高度10级floor量化，材料是假设Cauchy而非实测。
raw单位为单位入瞳功率下um^-2，积分须乘像元面积；normalized_psf=raw/raw.sum，仅ROI内概率质量。标准25波长ROI/入瞳捕获份额实测{lo:.9%}–{hi:.9%}；不是全能量99%收集。原归一化误差及所有能量见manifest。

## 3. RGB与旧前向流程

物理响应：`{sensor_path}`，400–700nm/10nm，文件波长单位um；数据键red/green/blue对应输出索引0/1/2。提取原response_curve函数执行红蓝toy测试，输入两个带强度2/7得到RGB=[7,0,2]，通过。红/绿/蓝峰值对应约600/530/450nm，仅作曲线合理性核查，不能替代硬件标定。
全部三通道共同除以31点绿色响应和{response[1].sum():.12g}，没有逐通道自动曝光。旧response_curve无波长插值、无显式Delta-lambda、只按谱轴索引相乘。标准25波长是31点中的子集，546.1nm须显式插值，不能把25/26/更少通道直接传入31权重接口。绝对响应量纲/曝光/光子标定未提供；不应把相对离散权重当实测辐射响应。
HSICamera.render：每谱带计算原DeepLens PSF→render_psf→response_curve；返回线性传感器浮点值，没有gamma/uint8/颜色矩阵/自动归一化，噪声调用已注释。render_psf先双轴翻核，再reflect边界填充并分组conv2d，属于反射边界线性卷积，不是零边界或FFT周期图像卷积。默认201奇数核；512偶数N02核不可原样替换而假设输出尺寸/半像元中心不变。网络预测clamp和save_image可视化截断在下游，研究反演不可使用PNG作线性观测。
R06-2只在网络入口RGB→BGR，不能改动物理响应。本轮未加载网络或权重。新N02 PSF目前未接入HSICamera。
真实相机JSON像元约{12340/4504:.9f}um，与N02的1um不同；若未来采用1um虚拟传感器检验形状，应明确声明。若要模拟此相机，需面积积分而非直接resize；这属于待实现适配，不是本轮篡改旧模型。

## 4. 数据与环境

8个CAVE验证场景、共{sum(len(d['bands']) for d in datasets)}张PNG已实际逐文件读取并记录dtype、尺寸、范围及SHA。路径见manifest。原文件uint16，但现有CaveDataset用IMREAD_GRAYSCALE读成uint8后/255，损失16位精度；原基线保持只读。未来读真值应IMREAD_UNCHANGED并核对有效位深/统一缩放。N03-A本可用合成谱，不受CAVE读取阻塞。
Python {platform.python_version()}；NumPy {np.__version__}；SciPy {scipy.__version__}；PyTorch {torch.__version__}，实测可用。执行路径`{sys.executable}`，审计在CPU完成，CUDA/GPU见manifest；没有安装或升级环境。

## 5. G0问题表与最小修复

|等级|问题与证据|最小后续行动|
|---|---|---|
|阻断|原gates.json的G2 FAIL、G3_Numerics FAIL；R summary_v2与最新R2最终审计明确维持FAIL，局部证据不能认证全ROI与全部波长。周期/采样纹理可能参与空间编码；用同一未认证数组合成与反演不能消除这一风险。|先审核最新R2结论，按其建议在420nm既有8点比较16×16与8×8源像元求积；此步骤也不自动认证全域。之后需受控完整边界及全部必要波长验证再重新冻结。此处只建议，未执行。|
|高|原1um源像元内部求积尚未认证；425nm单圈物理模态未完全认证，546.1nm主盘/旁峰口径敏感。|保持同高度与同物理掩模，补足独立数值证据，禁止借放宽旧门槛给PSF改判。|
|中|1um光学网格与2.74um真实传感器pitch不一致，31权重接口不接受原生25波长。|通过G0后明确虚拟形状实验或真实面积积分路线，显式选择波长与权重；若采用波段积分能量则不重复乘Delta-lambda。|
|中|响应绝对量纲/材料色散未实测，ROI捕获份额显著依波长变化。|选择并声明仅形状编码，或raw与入瞳/ROI通光效率一致建模；不得重复计能量或宣称硬件优势。|
|低|CAVE现入口降至8bit。|未来独立适配16bit读取；N03-A合成真值无需修补旧基线。|

这里的N03 G0不同于历史N02 gates.json里的G0；历史G0 PASS仅是彼轮物理自测/协议审计，不等于本任务输入可信门通过。不能仅因原报告有PASS标签而越过仍失败的数值证据。也不把硬件标定缺失单独当作形状实验必须停止的理由。

## 6. 只读校验与交付

本次{len(checks)}项只读检查，失败{sum(not c['passed'] for c in checks)}项，包括现存PSF维度/非负/归一化、冻结高度/mask哈希、RGB toy、8场景数量、R2 {len(r2_manifest)}份封存产物哈希及输入前后哈希。历史B2冻结清单另有{len(missing_frozen)}份文件未迁入，完整缺项列表见manifest；没有把精选迁移说成原冻结全包齐全。检查PASS只证明现存文件完整与约定可追溯，不推翻物理数值门失败。
未构造A、未运行NNLS/Tikhonov/噪声/失配，无重建指标或新曲线，避免触发停止条件后继续实验。N03-A/B/C均未执行。建议暂不进入B。
新增审计脚本及本目录报告/manifest/日志/run_commands；无原核心代码或资产改动。执行耗时及Git状态见manifest和日志。请将本审计连同原R2最终审计交给ChatGPT审核，先决定是否补数值可信性证据；本次不自动执行后续路线。
'''
    (out / '00_audit.md').write_text(audit, encoding='utf-8')
    command = f'& \'{sys.executable}\' -B E:\\SH\\integration\\single_spiral_to_hsi\\n03_audit.py --output E:\\SH\\reports\\N03_recheck_unique'
    (out / 'run_commands.md').write_text('# 复跑命令\n\n工作目录E:\\SH；输出目录须尚不存在，脚本拒绝覆盖。\n\n```powershell\n' + command + '\n```\n\n只读输入；仅向指定新目录写审计报告。无环境安装、无传播或重建。\n', encoding='utf-8')
    summary = dict(decision=manifest['decision'], checks=len(checks), failures=sum(not c['passed'] for c in checks),
                   archived_psfs=len(rows), standard_bands=len(native), preservation=preservation,
                   seconds=time.perf_counter()-start, command=subprocess.list2cmdline([sys.executable, '-B', *sys.argv]),
                   git_after=git('status', '--short', '--untracked-files=all'))
    (out / 'logs/00_audit_run.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
