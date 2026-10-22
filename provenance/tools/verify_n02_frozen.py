import sys,os,json,importlib.util,hashlib,time
from pathlib import Path
import numpy as np
sys.dont_write_bytecode=True
root=Path(sys.argv[1]);out=Path(sys.argv[2]);guard='--guard' in sys.argv
if guard:
 # 运行时屏蔽两个旧工程与个人下载目录；若误读即失败。
 forbidden=['e:/spiraldoe_hsi','e:/deeplenshsi','c:/users/李咏晨/downloads']
 def audit(event,args):
  if event in ('open','os.listdir','os.scandir','os.chdir') and args:
   p=args[0]
   if isinstance(p,(str,bytes,os.PathLike)):
    s=os.path.abspath(os.fsdecode(p)).replace('\\','/').lower()
    if any(s==f or s.startswith(f+'/') for f in forbidden):raise PermissionError('迁移隔离检查拒绝源路径: '+s)
 sys.addaudithook(audit)
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
start=time.time();opt=module('migration_optics',root/'experiments/n02/optics.py')
old=root/'results/n02/n02_20261019_02';cfg=json.loads((old/'B2/config.json').read_text(encoding='utf-8'))
h=np.load(old/'B2/height_um.npy');mask=np.load(old/'B2/aperture_mask.npy');coord=(np.arange(h.shape[0])-(h.shape[0]-1)/2)*cfg['pitch_um']
d=dict(coord=coord,r2=coord[:,None]**2+coord[None,:]**2,mask=mask)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen=json.loads((old/'B2/frozen_sha256.json').read_text(encoding='utf-8'))
assert sha(old/'B2/height_um.npy')==frozen['height_um.npy']
assert sha(old/'B2/aperture_mask.npy')==frozen['aperture_mask.npy']
rows=[];errors=[]
import csv
std=list(csv.DictReader((old/'B2/standard_metrics.csv').open(encoding='utf-8-sig')))
for row in std:
 w=float(row['wavelength_nm'])
 with np.load(old/'B2/cases'/f'{w:g}nm.npz') as z:
  raw=z['raw_roi'];c=z['coords_um'];r=json.loads(z['record_json'].item());nr=opt.measure(raw,c,r,cfg,w)
  for key in ['peak_x_um','peak_y_um','outside_main_disk_ratio','main_lobe_energy_fraction','angle_raw_deg']:
   delta=abs(nr[key]-float(row[key]));assert delta<1e-12,(w,key,delta);errors.append(delta)
  assert nr['n02_status']==row['n02_status']
  assert np.max(abs(z['normalized_psf']-raw/raw.sum()))<1e-15
  rows.append(dict(wavelength_nm=w,record=nr))
# 用同一冻结高度检查相位、入瞳能量和光学库错误处理。
u,power=opt.field(d,h,546.1,cfg)
probe=dict(field_sha256=hashlib.sha256(np.ascontiguousarray(u).tobytes()).hexdigest(),power=power,field_energy=float(np.sum(abs(u)**2)*cfg['pitch_um']**2))
assert abs(probe['field_energy']-1)<1e-12
import torch
rng=np.random.default_rng(20261020);a=rng.normal(size=(64,64))+1j*rng.normal(size=(64,64));t=torch.tensor(a,dtype=torch.complex128)
v,stats=opt.baseline.asm_memory_bounded(t,546.1,1.,.1,2)
probe['asm_sha256']=hashlib.sha256(v.numpy().tobytes()).hexdigest();probe['asm_stats']=stats
try:opt.phase_from_height(-np.ones((8,8)),550)
except ValueError:probe['negative_height_rejected']=True
else:raise AssertionError('非法高度未被拒绝')
gates=json.loads((old/'gates.json').read_text(encoding='utf-8'));assert gates['G2']['status']==gates['G3_Numerics']['status']=='FAIL'
# 导入完整入口；不调用会启动新传播的 execute。
sys.path.insert(0,str(root/'experiments/n02'));module('migration_n02_run',root/'experiments/n02/run.py')
sys.path.insert(0,str(root/'experiments/n02_1c_r'));module('migration_p0b_run',root/'experiments/n02_1c_r/p0b_run.py')
sys.path.insert(0,str(root/'experiments/n02_1c_r2'));module('migration_r2_run',root/'experiments/n02_1c_r2/r2_run.py')
verify=module('migration_r2_verify',root/'experiments/n02_1c_r2/r2_verify.py')
r2=root/'results/n02_1c_r2/n02_1cr2_20261020_02';numerical=verify.numerical_verify(r2)
manifest=json.loads((r2/'artifact_manifest.json').read_text(encoding='utf-8'))
for p,digest in manifest.items():assert sha(r2/p)==digest,p
up=root/'results/n02_1c_r/n02_1cr_20261020_01';assert json.loads((up/'P0B_gate_decision_v2.json').read_text(encoding='utf-8'))['status']=='INCONCLUSIVE'
status=json.loads((r2/'manifest.json').read_text(encoding='utf-8'))['scientific_status']
result=dict(status='PASS',guard_enabled=guard,height_file_sha256=sha(old/'B2/height_um.npy'),mask_file_sha256=sha(old/'B2/aperture_mask.npy'),probe=probe,standard_records=rows,max_frozen_metric_error=max(errors),r2_numerical=numerical,r2_output_hashes=len(manifest),scientific_status=status,old_G2_G3='FAIL_UNCHANGED',seconds=time.time()-start)
with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else v)
print(json.dumps({k:v for k,v in result.items() if k not in ['standard_records','probe']},ensure_ascii=False,indent=2))
