"""N02-1C-R 公共工具：旧文件只读，新文件独占创建。"""
import sys
sys.dont_write_bytecode=True
import os
import csv
import json
import hashlib
import importlib.util
import platform
import subprocess
import ctypes
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import scipy
import torch

ROOT=Path(__file__).resolve().parents[2]
CODE=Path(__file__).resolve().parent
OLD=ROOT/'results/n02/n02_20261019_02'
TASK=Path('C:/Users/李咏晨/Downloads/N02_%E5%AE%A1%E6%A0%B8%E4%B8%8E%E4%B8%8B%E4%B8%80%E8%BD%AECodex%E4%BB%BB%E5%8A%A1%E4%B9%A6_20261020.md')


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


old=load_module('p0b_frozen_optics',ROOT/'experiments/n02/optics.py')
sys.path.insert(0,str(CODE))


def now():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def arrsha(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,np.generic):return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v):return None
    if isinstance(v,Path):return str(v)
    return v


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(clean(value),f,ensure_ascii=False,indent=2,allow_nan=False)


def textfile(path,content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:f.write(content)


def csvwrite(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        w.writerows([{k:json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(dict,list,tuple,np.ndarray)) else clean(v) for k,v in r.items()} for r in rows])


def csvread(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def npz(path,**items):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:np.savez_compressed(f,**items)


def loadcase(path):
    with np.load(path,allow_pickle=False) as z:
        return z['raw_roi'].copy(),z['coords_um'].copy(),json.loads(z['record_json'].item())


def event(out,**items):
    with (out/'execution_ledger.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(clean(dict(time=now(),**items)),ensure_ascii=False,allow_nan=False)+'\n');f.flush()


def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True,encoding='utf-8')


def memory():
    class Mem(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['total_phys','avail_phys','total_page','avail_page','total_virtual','avail_virtual','avail_extended']]
    m=Mem();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    class PM(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(k,ctypes.c_size_t) for k in ['peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile']]
    p=PM();p.cb=ctypes.sizeof(p)
    ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(ctypes.windll.kernel32.GetCurrentProcess()),ctypes.byref(p),ctypes.sizeof(p))
    free,total=torch.cuda.mem_get_info() if torch.cuda.is_available() else (0,0)
    return dict(ram_available_bytes=m.avail_phys,ram_total_bytes=m.total_phys,cpu_peak_working_set_bytes=p.peak_working,
                cpu_working_set_bytes=p.working,gpu_free_bytes=free,gpu_total_bytes=total)


def snapshot():
    result={}
    for parent,dirs,files in os.walk(ROOT):
        dirs[:]=[n for n in dirs if n not in ['.git','n02_1c_r','__pycache__']]
        for name in files:
            p=Path(parent)/name;s=p.stat();rec=dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns)
            if p.suffix.lower() in ['.py','.json','.yaml','.md','.csv','.txt']:rec['sha256']=sha(p)
            result[p.relative_to(ROOT).as_posix()]=rec
    return result


def pupil():
    cfg=read(OLD/'B2/config.json')
    h=np.load(OLD/'B2/height_um.npy',allow_pickle=False);h.setflags(write=False)
    mask=np.load(OLD/'B2/aperture_mask.npy',allow_pickle=False)
    c=(np.arange(h.shape[0])-(h.shape[0]-1)/2)*cfg['pitch_um']
    return cfg,h,dict(coord=c,r2=c[:,None]**2+c[None,:]**2,mask=mask)


def input_field(d,h,w,cfg):
    """独立回代固定高度，不调用设计或任何取模/量化。"""
    wl=w/1000.;s=cfg['object_mm']*1000
    dist=np.sqrt(s*s+d['r2']);a=s/dist*d['mask'];power=float(np.sum(a*a)*cfg['pitch_um']**2)
    a=a/np.sqrt(power);n=1.5292+.008/wl**2
    phase=2*np.pi/wl*((n-cfg['n_env'])*h+d['r2']/(dist+s))
    return a*np.exp(1j*phase),power


def independent_metrics(raw,c,w,cfg,center=None):
    from scipy.ndimage import label,maximum_filter
    rr,cc=np.unravel_index(raw.argmax(),raw.shape);dx=float(c[1]-c[0]);total=float(raw.sum()*dx*dx)
    x,y=(float(c[cc]),float(c[rr])) if center is None else center
    disk_radius=1.22*(w/1000)*cfg['sensor_mm']*1000/(2*cfg['R_um'])
    yy,xx=np.meshgrid(c,c,indexing='ij');disk=(xx-x)**2+(yy-y)**2<=disk_radius**2
    side=float(raw[~disk].max());mx=(raw==maximum_filter(raw,size=3,mode='constant'))&~disk
    distinct=float(raw[mx].max()) if mx.any() else 0.
    return dict(roi_energy_incident=total,main_disk_energy_incident=float(raw[disk].sum()*dx*dx),
       main_disk_fraction_roi=float(raw[disk].sum()/raw.sum()),disk_radius_um=disk_radius,
       outside_ratio=float(raw.max()/side),distinct_ratio=float(raw.max()/distinct) if distinct else None,
       halfmax_components=int(label(raw>=.5*raw.max())[1]),peak_pixel_x_um=float(c[cc]),peak_pixel_y_um=float(c[rr]),
       peak_sample_intensity=float(raw.max()),side_sample_intensity=side)
