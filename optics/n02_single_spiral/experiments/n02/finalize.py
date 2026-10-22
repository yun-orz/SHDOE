"""计算批次完成后的独立归档入口，技术失败记录原样保留。"""
import sys
sys.dont_write_bytecode=True
import argparse
import json
from optics import ROOT
from reporting import finalize

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    out=ROOT/'results/n02'/args.run_id
    assert (out/'G3.json').exists()
    finalize(out,json.loads((out/'environment.json').read_text(encoding='utf-8')),None)
