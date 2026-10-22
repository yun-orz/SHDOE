import os,csv,json,hashlib,re,collections
from pathlib import Path
R=Path('E:/SH');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=R/'provenance/manifests/copied_files_sha256.csv';rows=list(csv.DictReader(manifest.open(encoding='utf-8-sig')));known={r['target'] for r in rows}
# 仅补充原始源码快照，不改变既有复制记录。
for p in (R/'provenance/source_code_originals').rglob('*.py'):
 if str(p) in known:continue
 source=Path('E:/SpiralDOE_HSI/n00_run_20261009')/p.relative_to(R/'provenance/source_code_originals');digest=sha(p)
 before=json.loads((R/'provenance/manifests/source_A_inventory.json').read_text(encoding='utf-8'));record=next(r for r in before if r['source']==str(source));assert digest==record['sha256']
 rows.append(dict(source=str(source),target=str(p),bytes=str(p.stat().st_size),source_sha256=digest,copied_sha256=digest,status='MATCH'))
with manifest.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
adapt=json.loads((R/'provenance/audit/code_adaptations.json').read_text(encoding='utf-8'));adapted={r['path'] for r in adapt}
for item in adapt:
 item['hash_semantics']='before_sha256/after_sha256为UTF-8 LF规范化文本SHA；复制与最终实际字节SHA见copied_files_sha256.csv与target_current_sha256.csv'
 item['actual_current_file_sha256']=sha(Path(item['path']))
(R/'provenance/audit/code_adaptations.json').write_text(json.dumps(adapt,ensure_ascii=False,indent=2),encoding='utf-8')
current=[]
for row in rows:
 p=Path(row['target']);digest=sha(p);status='SOURCE_MATCH' if digest==row['source_sha256'] else 'ADAPTED_RECORDED'
 assert status=='SOURCE_MATCH' or str(p) in adapted,p
 current.append(dict(target=str(p),current_sha256=digest,source_sha256=row['source_sha256'],status=status,bytes=p.stat().st_size))
with (R/'provenance/manifests/target_current_sha256.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(current[0]));w.writeheader();w.writerows(current)
files=[];links=[];cache=[];activepaths=[]
for base,dirs,names in os.walk(R,followlinks=False):
 for name in dirs+names:
  p=Path(base)/name
  if p.stat(follow_symlinks=False).st_file_attributes & 0x400:links.append(str(p))
 for name in names:
  p=Path(base)/name;rel=p.relative_to(R).as_posix();files.append((rel,p.stat().st_size))
  if '__pycache__' in p.parts or p.suffix=='.pyc':cache.append(rel)
  if p.suffix in ['.py','.yaml','.yml'] and p.stat().st_size<2**20:
   for n,line in enumerate(p.read_text(encoding='utf-8-sig',errors='replace').splitlines(),1):
    if re.search(r'E:[\\/](?:SpiralDOE_HSI|DeepLensHSI)|C:[\\/].*Downloads|file:///home/conda',line,re.I):
     category='PROVENANCE_READONLY_OR_GUARD' if rel.startswith('provenance/') else 'HISTORICAL_AUDIT_ONLY'
     activepaths.append(dict(file=rel,line=n,classification=category,text=line[:1000]))
assert not links,links
assert not cache,cache
stats=collections.defaultdict(lambda:dict(files=0,bytes=0))
for rel,size in files:
 k='/'.join(Path(rel).parts[:2]) if rel.startswith(('optics/','framework/','integration/')) else Path(rel).parts[0]
 stats[k]['files']+=1;stats[k]['bytes']+=size
summary=dict(status='PASS',copied_file_count=len(rows),copied_bytes=sum(int(r['bytes']) for r in rows),source_matching_current=sum(r['status']=='SOURCE_MATCH' for r in current),adapted_current=sum(r['status']=='ADAPTED_RECORDED' for r in current),workspace_files=len(files),workspace_bytes=sum(x[1] for x in files),modules=stats,links=links,unexpected_bytecode_caches=cache,old_source_code_references=activepaths,large_files=[dict(path=p,bytes=s) for p,s in files if s>100*2**20],note='工作区统计在最终报告生成前采样，包含参考与本次新输出；provenance里旧源路径用于只读审计。')
with (R/'provenance/migration_reports/target_integrity_audit.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in summary.items() if k not in ['old_source_code_references','large_files']},ensure_ascii=False,indent=2))
