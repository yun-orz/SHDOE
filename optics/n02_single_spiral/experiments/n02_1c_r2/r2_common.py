"""R2独占输出、只读历史和资源记录。"""
import sys
sys.dont_write_bytecode=True
import os,json,csv,hashlib,importlib.util,time,subprocess,platform,shutil
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import torch
import scipy

ROOT=Path(__file__).resolve().parents[2]
CODE=Path(__file__).resolve().parent
OLD=ROOT/'results/n02/n02_20261019_02'
UP=ROOT/'results/n02_1c_r/n02_1cr_20261020_01'
TASK=ROOT/'results/n02_1c_r2/n02_1cr2_20261020_02/task_original.md'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


base=module('r2_previous_common',ROOT/'experiments/n02_1c_r/p0b_common.py')
sys.path.insert(0,str(CODE))
memory=base.memory


def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def ahash(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,complex):return dict(real=x.real,imag=x.imag)
    if isinstance(x,float) and not np.isfinite(x):return None
    if isinstance(x,Path):return str(x)
    return x


def write(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(clean(obj),f,ensure_ascii=False,indent=2,allow_nan=False)


def textfile(path,s):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:f.write(s)


def csvwrite(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        w.writerows([{k:json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(dict,list,tuple,np.ndarray)) else clean(v) for k,v in r.items()} for r in rows])


def csvread(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def npz(path,**a):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:np.savez_compressed(f,**a)


def loadcase(path):
    with np.load(path,allow_pickle=False) as z:return z['raw_roi'].copy(),z['coords_um'].copy(),json.loads(z['record_json'].item())


def event(out,**obj):
    with (out/'execution_ledger.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(clean(dict(time=now(),**obj)),ensure_ascii=False,allow_nan=False)+'\n');f.flush()


def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True,encoding='utf-8')


def snapshot():
    result={}
    for parent,dirs,files in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in ['.git','n02_1c_r2','__pycache__']]
        for n in files:
            p=Path(parent)/n;s=p.stat();v=dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns)
            if p.suffix.lower() in ['.py','.json','.yaml','.csv','.md','.txt']:v['sha256']=sha(p)
            result[p.relative_to(ROOT).as_posix()]=v
    return result


def source_pixels():
    cfg=read(OLD/'B2/config.json');h=np.load(OLD/'B2/height_um.npy');mask=np.load(OLD/'B2/aperture_mask.npy')
    h.setflags(write=False);mask.setflags(write=False)
    coord=np.arange(h.shape[0])-(h.shape[0]-1)/2;yy,xx=np.meshgrid(coord,coord,indexing='ij')
    x=xx[mask];y=yy[mask];height=h[mask];s=cfg['object_mm']*1000
    power=float(np.sum(s*s/(s*s+x*x+y*y)))
    return cfg,h,mask,dict(x=x,y=y,height=height,K=1/np.sqrt(power),incident_midpoint_power=power,pixel_area_um2=1.)
