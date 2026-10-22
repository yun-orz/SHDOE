"""只读审计和历史保护快照；全部新证据写入 N02。"""
import sys
sys.dont_write_bytecode = True
import os
import json
import subprocess
import platform
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np
import torch
import scipy
from optics import ROOT, sha, config, cauchy

EXP = Path(__file__).resolve().parent


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x))


def textfile(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(content)


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True, encoding='utf-8')


def snapshot():
    result = {}
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in ['.git', 'n02', '__pycache__']]
        for name in files:
            p = Path(root)/name
            st = p.stat()
            item = dict(bytes=st.st_size, mtime_ns=st.st_mtime_ns)
            if p.suffix.lower() in ['.py', '.md', '.yaml', '.json', '.csv', '.txt']:
                item['sha256'] = sha(p)
            result[p.relative_to(ROOT).as_posix()] = item
    return result


def audit(out):
    write(out/'preservation_before.json', snapshot())
    textfile(out/'git_status_before.txt', git('status', '--short'))
    cfg = config()
    env = dict(time=now(), python=sys.executable, python_version=sys.version, platform=platform.platform(),
        numpy=np.__version__, scipy=scipy.__version__, torch=torch.__version__, cuda=torch.version.cuda,
        cuda_available=torch.cuda.is_available(), gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        seed=cfg['seed'], git_head=git('rev-parse','HEAD').strip(),
        disk_free_bytes=__import__('shutil').disk_usage(ROOT).free)
    write(out/'environment.json', env)
    inputs = [ROOT/'src/spiral_hsi/optics/propagation.py', ROOT/'src/spiral_hsi/optics/phase_from_height.py',
        ROOT/'experiments/N01_1/model.py', ROOT/'experiments/N01_2A/model.py',
        ROOT/'experiments/N01_2E_multiorder_pilot/run.py',
        ROOT/'experiments/N01_3A_G2_f2_q6_13wave/support.py',
        ROOT/'experiments/N01_2E_m12_branch_diagnostic/analyze.py',
        ROOT/'results/N01_3A_G2_f2_q6_13wave/g2_20261016_01/acquisition_plan.json',
        ROOT/'results/N01_3A_G3_f2_q6_blue_dense/g3_20261016_01/hypothesis_and_endpoints.json',
        ROOT/'results/N01_3A_G5_f2_q6_candidate_sensitivity/g5_20261017_01/summary.md',
        ROOT/'reports/N01_2A/N01_2A_固定高度DOE波长旋转可行性研究报告.md',
        ROOT.parent/'N02_单孔径低浮雕波长旋转单螺旋DOE设计方案_MF_SH_DOE.md',
        Path('C:/Users/李咏晨/Downloads/N02_MF_SH_DOE_Codex_%E5%AE%8C%E6%95%B4%E6%89%A7%E8%A1%8C%E8%A7%84%E5%88%92.md')]
    write(out/'input_hashes.json', {str(p):sha(p) for p in inputs})
    cfg['diameter_um'] = 2*cfg['R_um']
    write(out/'config_resolved.json', cfg)
    histcfg = json.loads(inputs[7].read_text(encoding='utf-8-sig'))['config']
    hyp = json.loads(inputs[8].read_text(encoding='utf-8-sig'))
    protocol = dict(n01_thresholds=histcfg['thresholds'], peak_analysis=hyp['peak_analysis'],
        n02_proposal=cfg['n02_proposal'],
        convergence=dict(shape_l1_max=.05, peak_shift_um_max=2., angle_deg_max=3., edge_fraction_max=.001,
            disk_ratio_abs_change_max=.10, incident_main_energy_abs_change_max=.01),
        dense_adaptive_rule='对 420–500nm 中 N02 峰比小于1.60、形态失败或链接不唯一的5nm邻段，每段新增1/2/3/4nm点，合并去重；最多80新增点',
        uncertainty='像素/亚像素角差与跨网格差仅误差代理；不构造虚假统计置信区间',
        p3_caveat='原提取器的NMS及refine按1um像素解释；只用于原1um协议，0.5um仅做物理指标收敛，不重定义冻结链接器',
        material='ASSUMED: 任务书给定Cauchy，未标定IP-Dip2；常数及折射率±0.005敏感性',
        energy='相对单位入瞳能量=1，raw强度单位um^-2；总域Parseval与无限空间收集效率分开；不含界面反射/吸收',
        stop='前向测试失败停止；科学失败保留。数值不收敛禁止G6/G7/G8。G5仅在基础模型无错误时有限诊断扫描。',
        scan_budget='G2/G3失败仅运行固定R粗扫6候选×25波长，不因失败无限搜索；P1/P2依赖未满足记NOT_TESTED')
    write(out/'protocol_frozen.json', protocol)
    paths='\n'.join(f'- `{p}`' for p in inputs)
    textfile(out/'N02-0_repository_audit.md', f'''# N02-0 仓库审计

真实根目录：`{ROOT}`；Git HEAD：`{env['git_head']}`；起始dirty清单见git_status_before.txt。
默认系统Python只有CPU版本torch，选用现有`{sys.executable}`，未安装依赖。
设备：{env['gpu']}；可用磁盘：{env['disk_free_bytes']/2**30:.2f} GiB。
N00/N01历史不改写；仅新建configs/n02、experiments/n02、results/n02、reports/n02。
保护快照记录全部历史文件size/mtime，文本额外SHA；不声称历史全部二进制内容哈希。

## 真实入口与冻结依据
{paths}

N01-2A：W/C同为R=1000um,f=20mm,550nm设计,400–700nm,熔融石英,18cm物距,22.495mm探测面。
W=14/31有效；C=31/31有效及-82.2099°，数值来自冻结报告，不重新实验。高度以原metadata及height文件为准，历史方案文档的55.488um与报告55.505um不一致，保留差异。
F2-q6：等面积L8、q6/G3；13点12/13有效，蓝端410/415nm双峰，G5证实候选截断敏感。
全部历史为NON-FAIR REFERENCE，材料、几何、波段不同，不作严格优越性证明。
''')
    n = float(cauchy(.5461)); p = .5461/(n-1)
    textfile(out/'N02-0_physics_audit.md', f'''# N02-0 物理/指标审计

ASSUMED 材料：n(λ_um)=1.5292+0.00800/λ_um²；n(546.1nm)={n:.12f}，与1.556差{n-1.556:.12g}；p={p:.12f}um，Q10上限={.9*p:.12f}um。
DERIVED: NF={500**2/(2*.5461*20000):.9f}；解析角只作先验，不作实验结论。
球面入射相位正号，聚焦设计相位负号，高度相位正号；exp(-iωt)和正向ASM核一致。
nm输入波长，um横向/高度，mm传播；FFT未shift坐标的频点与居中补零一致。
坐标像素中心为(i-(N-1)/2)dx，x向右y向上；ROI边界±256um。孔径与高度分离。
传播复用N01-1 asm_memory_bounded，complex128；N00核、SciPy独立ASM/Fresnel复核。
未修订旧检测器：4邻接半峰连通域；主盘1.22λz/D，主峰像素值/主盘外最大像素值；独立旁峰为3×3局部极值。
旧阈值1.25与N02提案1.50同时输出。半峰域1、稳定3×3对数二次拟合、主峰非轴心及ROI内要求保留。
冻结P3：5%候选，最多12峰，主盘半径NMS，21×21补丁，距离≤15um，径向≤6um，角≤70°，强度倍数≤4，余弦≥.65；必须保留全部可行边与未匹配峰。
冻结链接有限候选集唯一不等于同一物理模态，历史G5发现截断敏感，不能隐去此风险。
蓝端5nm角差门按10nm的4–18°线性缩放；原45°启发式和P3门不改变。
能量基准为归一的入瞳1；另存未归一入瞳面积功率，ROI归一只用于形态和相关性。
标量薄相位模型未包含矢量/侧壁/吸收反射，不等于加工或实测。
任务书两条外部DOI在线读取失败，未据此确认IP-Dip2色散与工艺；不冒充读过原文。
''')
    return env
