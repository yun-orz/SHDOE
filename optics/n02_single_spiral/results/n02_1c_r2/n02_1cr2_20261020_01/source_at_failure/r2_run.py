"""R2唯一执行入口，逐阶段保留输入、失败和资源跳过。"""
import sys
sys.dont_write_bytecode=True
import argparse,traceback
from r2_common import *
from r2_prepare import prepare
from r2_solver import self_tests
from r2_experiments import run_p1,run_p2,check_p3
from r2_analysis import analyze_p1,analyze_p2
from r2_report import finalize


def execute(out):
    start=time.perf_counter();cfg,h,mask,src,env,resource,plan,peak=prepare(out)
    event(out,event='P0_AUDIT_PREREGISTERED',resource=resource,points=len(plan),height_sha256=sha(OLD/'B2/height_um.npy'))
    tests=self_tests(cfg,src);write(out/'implementation_tests.json',tests)
    assert all(r['status']=='PASS' for r in tests),'实现自测失败，后续传播停止'
    print('P0审计和5项独立实现自测通过，预注册点',len(plan),flush=True)
    p1=run_p1(out,cfg,src,resource,plan);a1=analyze_p1(out,p1)
    p2=run_p2(out,cfg,src,resource,peak,p1);a2=analyze_p2(out,peak,p2)
    check_p3(out)
    finalize(out,cfg,env,resource,p1,a1,p2,a2,start)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    if any(x in args.run_id for x in ['..','/','\\']):raise ValueError('run-id必须是单一目录名')
    out=ROOT/'results/n02_1c_r2'/args.run_id;out.mkdir(parents=True,exist_ok=False)
    write(out/'invocation.json',dict(time=now(),argv=sys.argv,python=sys.executable))
    try:execute(out)
    except Exception:
        textfile(out/'failure_traceback.txt',traceback.format_exc());raise
