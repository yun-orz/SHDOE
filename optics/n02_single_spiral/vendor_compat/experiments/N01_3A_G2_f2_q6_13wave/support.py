"""限定阶段的文件工具；仅导入封存的纯函数。"""
import sys
sys.dont_write_bytecode=True
import os
import json
import csv
import math
import hashlib
import importlib.util
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
EXP=Path(__file__).resolve().parent
STAGE=EXP.name
G1=ROOT/'results/N01_3A_G1_equal_area_linear_offset/g1_20261016_01'
F1=ROOT/'results/N01_2F_G2_f1_13wave/g2_20261015_01'
P3=ROOT/'results/N01_2E_m12_branch_diagnostic/p3_20261015_01'
WAVES=list(range(400,701,25))
REUSED=[400,550,700]
NEW=[w for w in WAVES if w not in REUSED]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

runtime=module('frozen_g2_runtime',ROOT/'experiments/N01_2F_G2_f1_13wave/runtime.py')
old,legacy=runtime.old,runtime.legacy
# P3分析文件使用绝对runtime导入，只在加载时临时绑定原模块，随后恢复。
previous=sys.modules.get('runtime')
sys.modules['runtime']=module('frozen_p3_runtime',ROOT/'experiments/N01_2E_m12_branch_diagnostic/runtime.py')
p3=module('frozen_p3_analysis',ROOT/'experiments/N01_2E_m12_branch_diagnostic/analyze.py')
if previous is None:sys.modules.pop('runtime')
else:sys.modules['runtime']=previous

sha=old.sha
write=old.write_json
csvwrite=old.write_csv
load=runtime.load

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def objsha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def array_sha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def event(path,**value):
    with Path(path).open('a',encoding='utf-8') as f:
        f.write(json.dumps(dict(time=now(),**value),ensure_ascii=False,allow_nan=False)+'\n');f.flush()

def snapshot():
    """保护整个工程的旧文件清单、大小、mtime；关键输入另做内容哈希。"""
    files={};directories=[]
    for current,dirs,names in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in ['.git',STAGE]]
        directories.extend((Path(current)/d).relative_to(ROOT).as_posix() for d in dirs)
        for name in names:
            p=Path(current)/name;s=p.stat()
            files[p.relative_to(ROOT).as_posix()]=dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns)
    return dict(scope='整个工程排除.git及本阶段代码/结果目录；仅文件清单/大小/mtime及目录清单，不冒称全部内容哈希；关键输入另见input_hashes.json',
                files=files,directories=sorted(directories))

def phase_free_record(raw,c,r,cfg,w):
    """检测只调用冻结版本，新增字段不反馈给检测器。"""
    measured=runtime.add_competition(old.lobe_record(raw,c,r,cfg,w))
    pixelangle=math.degrees(math.atan2(measured['argmax_y_um'],measured['argmax_x_um']))
    lobe=measured['main_lobe_radius_um']
    measured.update(pixel_fit_angle_offset_deg=abs((measured['angle_raw_deg']-pixelangle+180)%360-180),
        angle_usage='有效形态的原始角度，分支需另证' if measured['status']=='VALID' else '仅诊断角度',
        gate_halfmax_unique=measured['halfmax_components']==1,
        gate_outside_disk_ratio=measured['main_sidelobe_ratio']>=cfg['thresholds']['outside_disk_ratio'],
        gate_distinct_peak_ratio=measured['distinct_side_ratio'] is None or measured['distinct_side_ratio']>=cfg['thresholds']['distinct_peak_ratio'],
        gate_fit=measured['subpixel_fit'],gate_radius=measured['peak_radius_um']>2*cfg['pitch_um'],
        near_roi_boundary=abs(measured['peak_x_um'])>256-lobe or abs(measured['peak_y_um'])>256-lobe,
        gate_global_peak=measured['global_peak_in_roi'])
    return measured
