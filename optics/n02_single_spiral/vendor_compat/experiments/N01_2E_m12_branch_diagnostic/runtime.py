"""只读导入原模型及确定性工具；本阶段不调用旧入口。"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import importlib.util
import json
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
EXP = Path(__file__).resolve().parent
P1 = ROOT/'results/N01_2E_multiorder_pilot/pilot_20261015_01'
P2 = ROOT/'results/N01_2E_m12_7point/p2_20261015_01'
sys.path.insert(0, str(ROOT/'experiments/N01_2E_multiorder_pilot'))
spec = importlib.util.spec_from_file_location('p1_readonly_tools', ROOT/'experiments/N01_2E_multiorder_pilot/run.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
legacy = old.legacy
sha, write_json, write_csv, save_case = old.sha, old.write_json, old.csv_write if hasattr(old, 'csv_write') else old.write_csv, old.save_case


def load(path):
    with np.load(path, allow_pickle=False) as z:
        return z['raw_roi'].copy(), z['coords_um'].copy(), json.loads(z['record_json'].item())


def protection():
    roots = [P1, P2, ROOT/'experiments/N01_2E_multiorder_pilot', ROOT/'experiments/N01_2E_m12_7point']
    return {p.relative_to(ROOT).as_posix(): sha(p) for root in roots for p in sorted(root.rglob('*')) if p.is_file()}
