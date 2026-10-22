import json,sys,csv,time,importlib.metadata
from pathlib import Path
import numpy as np,torch
R=Path('E:/SH');N=R/'optics/n00_forward';D=R/'framework/DeepLensHSI'
with np.load(N/'reference_results/N00_verified/psf_cube.npz') as a,np.load(N/'results/migration_20261020/psf_cube.npz') as b:
 n00=dict(shape=list(b['PSF_cube'].shape),wavelength_equal=np.array_equal(a['wavelength_nm'],b['wavelength_nm']),height_equal=np.array_equal(a['height_um'],b['height_um']),max_psf_abs_difference=float(abs(a['PSF_cube']-b['PSF_cube']).max()),max_raw_intensity_abs_difference=float(abs(a['raw_intensity']-b['raw_intensity']).max()),max_normalization_error=float(abs(b['PSF_cube'].sum(axis=(1,2))-1).max()))
 assert n00['wavelength_equal'] and n00['height_equal'] and n00['max_psf_abs_difference']<1e-12
old=D/'reference_results/R05_validation';new=D/'results/R05_validation'
read=lambda p:list(csv.DictReader(p.open(encoding='utf-8-sig')))
a={r['scene']:r for r in read(old/'metrics.csv')};b={r['scene']:r for r in read(new/'metrics.csv')};assert a.keys()==b.keys() and len(b)==8
rows=[]
for scene,row in b.items():
 before=torch.load(old/scene/'spectra.pt',map_location='cpu',weights_only=True);after=torch.load(new/scene/'spectra.pt',map_location='cpu',weights_only=True)
 delta={key:float((before[key]-after[key]).abs().max()) for key in ['gt','pred']}
 assert all(torch.isfinite(after[k]).all() for k in ['gt','pred'])
 rows.append(dict(scene=scene,**delta,metric_differences={k:float(row[k])-float(a[scene][k]) for k in ['psnr_db','ssim','sam_deg','sam_valid_pct']}))
means={k:sum(float(r[k]) for r in b.values())/8 for k in ['psnr_db','ssim','sam_deg']}
comparison=dict(status='PASS' if all(max(abs(v) for v in r['metric_differences'].values())<1e-6 for r in rows) else 'PASS_WITH_DIFFERENCES',means=means,scenes=rows,reference_is_history=True,this_run_is_fresh_inference=True)
for name,data in [('N00_reference_comparison.json',n00),('DeepLens_reference_comparison.json',comparison)]:
 with (R/'provenance/migration_reports'/name).open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
env=dict(python=sys.version,executable=sys.executable,torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),numpy=np.__version__,packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()})
with (R/'environments/runtime_versions.json').open('x',encoding='utf-8') as f:json.dump(env,f,ensure_ascii=False,indent=2)
with (R/'environments/requirements_runtime.txt').open('x',encoding='utf-8') as f:
 f.write('--extra-index-url https://download.pytorch.org/whl/cu121\n')
 for k,v in sorted(env['packages'].items(),key=lambda kv:kv[0].lower()):f.write(k+'=='+v+'\n')
print('N00',json.dumps(n00));print('DeepLens',json.dumps(comparison));print('environment',env['python'],env['torch'])
