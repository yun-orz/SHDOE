"""保留技术中断记录，从已完成批次1继续，拒绝覆盖既有验证产物。"""
import sys
sys.dont_write_bytecode=True
import argparse
import json
import time
import traceback
from optics import ROOT,config,sha
from audit import write,textfile,now


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    out=ROOT/'results/n02'/args.run_id
    assert (out/'completion_summary_batch1.md').exists()
    attempt=str(time.time_ns())
    write(out/f'resume_invocation_{attempt}.json',dict(time=now(),argv=sys.argv,python=sys.executable,
        reason='原始批次1产物完整，后续validation模块补齐后续跑；保留failure_traceback.txt',
        source_hashes={p.name:sha(p) for p in (ROOT/'experiments/n02').glob('*.py')}))
    try:
        from validation import validate
        validate(out,dict(config(),candidate_id='B2'))
        from reporting import finalize
        finalize(out,json.loads((out/'environment.json').read_text(encoding='utf-8')),None)
    except Exception:
        textfile(out/f'resume_failure_traceback_{attempt}.txt',traceback.format_exc())
        raise
