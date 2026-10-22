import os,json,csv,hashlib,subprocess,difflib
from pathlib import Path
R=Path('E:/SH');D=R/'framework/DeepLensHSI';S=Path('E:/DeepLensHSI');P=R/'provenance';os.environ['GIT_OPTIONAL_LOCKS']='0'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
expected=json.loads((D/'reports/R06-2_channel_swap/metrics_summary.json').read_text(encoding='utf-8'))
actual=list(csv.DictReader((D/'results/R06_2_validation/metrics.csv').open(encoding='utf-8-sig')));assert len(actual)==8
ref={r['scene']:r for r in expected['per_scene']};mapping={'psnr_db':'psnr_B','ssim':'ssim_B','sam_deg':'sam_hist_B','sam_fixed_deg':'sam_fixed_B'}
errors=[]
for r in actual:
 assert r['scene'] in ref
 delta={k:float(r[k])-ref[r['scene']][v] for k,v in mapping.items()}
 # 容差预设为1e-4，覆盖历史GPU与本次CPU评价的浮点舍入；不按结果调整。
 assert all(abs(v)<=1e-4 for v in delta.values()),(r['scene'],delta)
 errors.append(dict(scene=r['scene'],differences=delta,psnr_improved_over_R05=float(r['psnr_db'])>ref[r['scene']]['psnr_A']))
assert all(r['psnr_improved_over_R05'] for r in errors)
means={k:sum(float(r[k]) for r in actual)/8 for k in mapping};assert means['psnr_db']>30
# 模型、传感器、DOE与样例均保持此前迁移的同一份字节。
copyrows=list(csv.DictReader((P/'manifests/copied_files_sha256.csv').open(encoding='utf-8-sig')))
protected=[]
for row in copyrows:
 p=Path(row['target'])
 if p.is_relative_to(D) and any(x in p.parts for x in ['ckpts','lenses','sensors','datasets','reference_results']):
  assert sha(p)==row['source_sha256'],p;protected.append(str(p))
# 复核源B所有文件，包括Git和未跟踪R06-2证据。
before=json.loads((P/'source_git_state/B_R06_2_update_before.json').read_text(encoding='utf-8'));old={r['path']:r for r in before['files']};seen=set();changes=[]
for base,dirs,files in os.walk(S):
 for n in files:
  p=Path(base)/n;rel=p.relative_to(S).as_posix();seen.add(rel);s=p.stat();row=old.get(rel)
  if row is None or (s.st_size,s.st_mtime_ns,sha(p))!=(row['bytes'],row['mtime_ns'],row['sha256']):changes.append(rel)
assert not changes and seen==old.keys(),changes
for args,expected_git in before['git'].items():
 out=subprocess.run(['git','--no-optional-locks','-C',str(S)]+args.split(),capture_output=True)
 actual_git=dict(returncode=out.returncode,stdout=out.stdout.decode('utf-8',errors='replace'),stderr=out.stderr.decode('utf-8',errors='replace'))
 assert actual_git==expected_git,args
summary=dict(status='PASS',means=means,per_scene_comparison=errors,reference_source='reports/R06-2_channel_swap/metrics_summary.json',max_absolute_metric_difference=max(abs(v) for row in errors for v in row['differences'].values()),protected_model_optics_data_files=len(protected),source_B_files=len(seen),source_B_all_sha256_size_mtime_and_git_unchanged=True,weight_sha256=sha(D/'ckpts/nafnet_hsi.pth'),network_input_order='BGR',physical_sensor_order='RGB',weight_file_modified=False,old_R05_preserved=True)
with (P/'migration_reports/R06_2_baseline_update_verification.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
print(json.dumps(summary,ensure_ascii=False,indent=2))
