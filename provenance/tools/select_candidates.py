import sys, os, json, csv, shutil, re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
# 这里只读盘点结果，不重新执行源目录盘点。
ROOT=Path('E:/SH'); A=Path('E:/SpiralDOE_HSI/n00_run_20261009');B=Path('E:/DeepLensHSI')
N00='optics/n00_forward';N02='optics/n02_single_spiral';DL='framework/DeepLensHSI'
legacy=['N01_3A_G2_f2_q6_13wave/support.py','N01_2F_G2_f1_13wave/runtime.py','N01_2E_m12_branch_diagnostic/runtime.py','N01_2E_m12_branch_diagnostic/analyze.py','N01_2E_multiorder_pilot/run.py','N01_2E_multiorder_pilot/model.py','N01_2A/model.py','N01_1/model.py']
val=[x.strip().removeprefix('./')+'/' for x in (B/'datasets/cave_val.txt').read_text().splitlines() if x.strip()]
rows=[];selected=[];scans=[]
def add(r,label,target,reason,cls='COPY_REQUIRED',ref=''):
 item=dict(r,origin=label,target=str(ROOT/target) if target else '',classification=cls,reason=reason,retention='working_snapshot' if target else 'source_archive',referenced_by=ref)
 rows.append(item)
 if target:selected.append(item)
for label,source in [('A',A),('B',B)]:
 for r in json.loads((ROOT/f'provenance/manifests/source_{label}_inventory.json').read_text(encoding='utf-8')):
  p=r['relative'];parts=Path(p).parts;destinations=[]
  cache=any(x in parts for x in ['.git','__pycache__','.bridge-cache','.idea']) or p.endswith('.pyc')
  if not cache and label=='B':
   if p.startswith(('src/','configs/','sensors/')) or ('/' not in p and (p.endswith('.py') or p.lower().startswith(('readme','license','copying','environment','.gitignore')))):
    destinations.append((f'{DL}/{p}','推理验证源码、配置与许可'))
   if p in ['ckpts/nafnet_hsi.pth','lenses/paraxiallens/doelens_hsi.json','lenses/paraxiallens/planar_doe.npy','datasets/cave_val.txt'] or any(p.startswith(v) for v in val):
    destinations.append((f'{DL}/{p}','预训练权重、冻结光学输入或8场景验证数据'))
   if p.startswith('reports/R05') or p.startswith('results/R05_validation/'):
    target=f'{DL}/reference_results/'+p[len('results/'):] if p.startswith('results/') else f'{DL}/{p}'
    destinations.append((target,'历史R05参考；与本次输出分开'))
   if Path(p).name.lower().startswith(('license','copying')) and not destinations:destinations.append((f'{DL}/{p}','第三方许可'))
  if not cache and label=='A':
   if p.startswith(('src/','scripts/','tests/','docs/','reports/N00/')) or p in ['README.md','requirements.txt','.gitignore','configs/n00_baseline.yaml']:
    destinations.append((f'{N00}/{p}','N00计算、测试与验收依据'))
   if p.startswith('results/N00_verified/'):
    destinations.append((f'{N00}/reference_results/N00_verified/'+p[len('results/N00_verified/'):],'唯一N00冻结参考'))
   if p.startswith('src/'):
    destinations.append((f'{N02}/{p}','N02直接使用N00光学库'))
    destinations.append((f'{N02}/vendor_compat/{p}','旧兼容模块相对导入所需原样光学库'))
   if any(p.startswith(prefix+branch+'/') for prefix in ['configs/','experiments/','reports/'] for branch in ['n02','n02_1c_r','n02_1c_r2']):
    destinations.append((f'{N02}/{p}','当前三个N02分支源码、配置与报告'))
   if p in ['experiments/'+x for x in legacy]:
    destinations.append((f'{N02}/vendor_compat/{p}','动态导入闭包；仅8个旧源码文件，不带旧结果'))
   if p.startswith(('results/n02_1c_r/','results/n02_1c_r2/')):
    destinations.append((f'{N02}/{p}','R诊断与R2两轮完整证据；保持相对读取路径'))
   prefix='results/n02/n02_20261019_02/'
   if p.startswith(prefix):
    tail=p[len(prefix):];needed=False
    if '/' not in tail:needed=True
    elif tail.startswith('B2/'):
     if '/cases/' not in tail:needed=True
     else:
      w=float(Path(tail).stem.removesuffix('nm'))
      needed=w in set(range(420,661,10))|set(range(420,431))|{546.1}
    elif tail.startswith('convergence/cases/'):needed=True
    if needed:destinations.append((f'{N02}/{p}','B2标准25波长、蓝端420–430nm、546.1nm及冻结收敛闭包'))
   if p.startswith('results/n02/n02_20261019_01/') and Path(p).suffix.lower() in ['.json','.md','.txt','.csv','.jsonl']:
    destinations.append((f'{N02}/{p}','首次N02运行最小失败/来源证据'))
  if destinations:
   for dest,reason in dict((x[0],x) for x in destinations).values():add(r,label,dest,reason,'REFACTOR_OR_VENDOR' if '/vendor_compat/' in dest else 'COPY_REQUIRED')
  else:add(r,label,None,'原位保留；缓存可再生成' if cache else '历史研究分支、训练数据或非必需产物','REGENERATE' if cache else 'LEAVE_SOURCE_ARCHIVE')
  if not cache and Path(p).suffix.lower() in ['.py','.json','.yaml','.yml','.md','.txt'] and r['bytes']<4*1024*1024:
   content=Path(r['source']).read_text(encoding='utf-8',errors='replace')
   for n,line in enumerate(content.splitlines(),1):
    if re.search(r'[A-Za-z]:[\\/]|file:///home/conda|/home/conda',line):scans.append(dict(source=r['source'],line=n,text=line[:1500],selected=bool(destinations)))
fields=list(rows[0])
for name,items in [('candidate_dry_run.csv',rows),('selected_files.csv',selected)]:
 path=ROOT/'provenance/manifests'/name
 with path.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
(ROOT/'provenance/audit/absolute_paths_scan.json').write_text(json.dumps(scans,ensure_ascii=False,indent=2),encoding='utf-8')
conflicts=[]
for r in selected:
 p=Path(r['target'])
 if p.exists():conflicts.append(str(p))
size=sum(r['bytes'] for r in selected);free=shutil.disk_usage(ROOT).free
report=dict(status='READY' if not conflicts and free>size*2 else 'BLOCKED',files=len(selected),bytes=size,free_bytes=free,existing_targets=conflicts,validation_scene_dirs=val,legacy_files=legacy,selection_rule='保持results相对路径；历史产物不改写；N02整包历史校验入口不重跑，它需要全部被排除的变体。迁移验证入口只验证已精选闭包。')
(ROOT/'provenance/migration_reports').mkdir(parents=True,exist_ok=True)
(ROOT/'provenance/migration_reports/M00_dry_run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
