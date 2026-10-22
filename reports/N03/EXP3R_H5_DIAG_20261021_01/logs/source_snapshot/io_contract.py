"""新交付目录内独占写入、旧文件哈希与Git状态冻结。"""
import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
CODE=Path(__file__).resolve().parent
BASE=ROOT/'reports/N03/EXP3R_BUDGET_AB_20261021_01'
EXP3=ROOT/'reports/N03/EXP3_UNKNOWN_POS_20261021_02'
NOTICE='EXPLORATORY / N03 G0 FAIL / N02 G2+G3_Numerics FAIL'


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def csvread(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def gitstate():
    def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
    return dict(head=git('rev-parse','HEAD').decode().strip(),
                porcelain_v2=git('status','--porcelain=v2').decode('utf-8').strip(),
                tracked_diff_sha256=hashlib.sha256(git('diff','--binary')).hexdigest())


class OutputWriter:
    def __init__(self,root):self.root=Path(root).resolve()
    def path(self,name):
        p=(self.root/name).resolve()
        if self.root not in p.parents:raise PermissionError('写入范围仅限本次新报告目录')
        return p
    def json(self,name,obj):
        with self.path(name).open('x',encoding='utf-8') as h:json.dump(obj,h,ensure_ascii=False,indent=2,allow_nan=False)
    def text(self,name,value):
        with self.path(name).open('x',encoding='utf-8') as h:h.write(value)
    def csv(self,name,rows):
        keys=list(dict.fromkeys(k for r in rows for k in r)) or ['status']
        with self.path(name).open('x',encoding='utf-8',newline='') as h:
            w=csv.DictWriter(h,fieldnames=keys);w.writeheader();w.writerows(rows)
