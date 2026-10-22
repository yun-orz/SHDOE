"""EXP2B独立产物、旧输入保护、命令与哈希记录。"""
import ast
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
import scipy
import torch

ROOT=Path(__file__).resolve().parents[3]
EXP2=ROOT/'reports/N03/EXP2_20261020_03'
CODE=Path(__file__).resolve().parent
NOTICE='EXP2B EXPLORATORY, archived PSFs; N03 G0 FAIL; N02 G2/G3_Numerics FAIL.'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


def textfile(path,value):
    with Path(path).open('x',encoding='utf-8') as f:f.write(value)


def csvwrite(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)


def csvread(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def git(*parts):return subprocess.check_output(['git','-C',str(ROOT),*parts],encoding='utf-8').strip()


def gitstate():
    return dict(head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),dirty=git('status','--short','--untracked-files=all'),
                tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(ROOT),'diff','--binary'])).hexdigest())


def environment(device):
    return dict(python=sys.version,executable=sys.executable,numpy=np.__version__,scipy=scipy.__version__,torch=torch.__version__,
                device=device,precision='float64 / complex128',platform=platform.platform(),time_Asia_Shanghai=datetime.now(timezone(timedelta(hours=8))).isoformat())


def task_source():
    path=Path('C:/Users/李咏晨/Downloads/N03-A-EXP2B_%E6%A0%87%E5%AE%9A%E5%AE%B9%E5%B7%AE%E4%B8%8EN02%E5%8F%97%E9%99%90%E6%95%B0%E5%80%BC%E7%AD%9B%E6%9F%A5_Codex%E4%BB%BB%E5%8A%A1%E4%B9%A6.md')
    return dict(path=str(path),sha256=sha(path))


def new_output(path):
    path=Path(path).resolve()
    if path.exists():raise FileExistsError(f'输出已存在，拒绝覆盖：{path}')
    path.mkdir(parents=True,exist_ok=False);(path/'logs').mkdir();(path/'figures').mkdir()
    return path


def event(out,started,stage,**details):
    obj=dict(seconds=time.perf_counter()-started,stage=stage,**details)
    with (out/'logs/events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
    print(json.dumps(obj,ensure_ascii=False),flush=True)


def freeze(out,paths):
    inputs={str(p.relative_to(ROOT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in dict.fromkeys(paths)}
    write(out/'input_manifest.json',inputs)
    (out/'logs/source_snapshot').mkdir()
    sources={}
    for p in list(CODE.glob('*.py'))+[CODE.parent/'tests/test_n03_exp2b.py']:
        target=out/'logs/source_snapshot'/p.name
        with target.open('xb') as f:f.write(p.read_bytes())
        sources[str(p.relative_to(ROOT))]=dict(sha256=sha(p),snapshot=str(target.relative_to(out)))
    write(out/'source_manifest.json',sources)
    return inputs


def verify_exp2():
    bad=[name for name,h in read(EXP2/'final_manifest.json').items() if sha(EXP2/name)!=h]
    if bad:raise RuntimeError(f'正式EXP2归档校验失败：{bad}')


def finish(out,started,status,before,inputs,**details):
    changed=[p for p,d in inputs.items() if sha(ROOT/p)!=d['sha256']]
    after=gitstate()
    if changed or before['tracked_diff_sha256']!=after['tracked_diff_sha256']:raise RuntimeError(f'旧资产保护失败：{changed}')
    command=subprocess.list2cmdline([sys.executable,'-B',*sys.argv])
    textfile(out/'run_commands.md','# 实际命令与复跑\n\n'+NOTICE+'\n\n工作目录E:\\SH，实际命令：\n\n```powershell\n'+command+'\n```\n\n复跑必须另选尚不存在的输出目录；OPENBLAS_NUM_THREADS、MKL_NUM_THREADS、OMP_NUM_THREADS均为4，PYTHONDONTWRITEBYTECODE=1，既有环境，无依赖安装。\n')
    write(out/'logs/run_record.json',dict(status=status,exit_code=0,seconds=time.perf_counter()-started,command=command,git_before=before,git_after=after,
                                        inputs_unchanged=True,environment=environment(details.pop('device','CPU')),**details))
    event(out,started,'DELIVERED',status=status)
    write(out/'artifact_manifest.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})


def extract_function(path,name,globals_dict):
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),globals_dict)
    return globals_dict[name],dict(path=str(path),line=fn.lineno,end_line=fn.end_lineno,sha256=sha(path))
