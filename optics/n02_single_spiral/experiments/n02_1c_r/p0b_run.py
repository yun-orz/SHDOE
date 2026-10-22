"""N02-1C-R唯一入口：只读审计优先，再受预算约束的A/B/C诊断。"""
import sys
sys.dont_write_bytecode=True
import argparse
import traceback
import time
from p0b_common import *
from p0b_analysis import audit,analyze_a,analyze_c
from p0b_propagation import plan_resources,self_tests
from p0b_boundary import run_b
from p0b_report import finalize


def execute(out):
    start=time.perf_counter();cfg,h,d,env=audit(out)
    protocol=read(ROOT/'configs/n02_1c_r/P0B_protocol_v1.json')
    write(out/'P0B_diagnostic_protocol.json',protocol)
    write(out/'protocol_preregistration.json',dict(time=now(),protocol_sha256=sha(out/'P0B_diagnostic_protocol.json'),
        input_hashes_sha256=sha(out/'input_hashes.json'),source_hashes={p.name:sha(p) for p in CODE.glob('*.py')}))
    event(out,event='READ_ONLY_AUDIT_COMPLETE',old_raw_cases=571,old_G2='FAIL',old_G3='FAIL',resource=memory())
    print('只读历史审计完成，571 NPZ / 900哈希；旧G2/G3 FAIL保留',flush=True)
    plan=plan_resources(out,cfg);tests=self_tests(cfg,h,d)
    write(out/'diagnostics/implementation_self_tests.json',tests)
    if not all(t['status']=='PASS' for t in tests):raise RuntimeError('独立实现自测失败，禁止新传播')
    aa=analyze_a(out);print('A：独立拟合、多估计器和合成峰测试完成',flush=True)
    cc=analyze_c(out,cfg);print('C：独立能量、像元和Gram复核完成',flush=True)
    bb=run_b(out,cfg,h,d,plan)
    finalize(out,env,aa,cc,bb,start)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    if any(x in args.run_id for x in ['..','/','\\']):raise ValueError('run-id必须为单目录名')
    out=ROOT/'results/n02_1c_r'/args.run_id;out.mkdir(parents=True,exist_ok=False)
    write(out/'invocation.json',dict(time=now(),python=sys.executable,argv=sys.argv))
    try:execute(out)
    except Exception:
        textfile(out/'failure_traceback.txt',traceback.format_exc());raise
