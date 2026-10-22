import csv,json,hashlib,os,subprocess,shutil,time
from pathlib import Path
R=Path('E:/SH');os.environ['GIT_OPTIONAL_LOCKS']='0'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
plan=json.loads((R/'provenance/migration_reports/M00_dry_run.json').read_text(encoding='utf-8'))
assert plan['status']=='READY',plan
rows=list(csv.DictReader((R/'provenance/manifests/selected_files.csv').open(encoding='utf-8-sig')))
# 先核实清单及所有目标冲突，再复制；不允许覆盖任何已有目标。
for r in rows:
 s=Path(r['source']);d=Path(r['target']);assert s.is_file() and not d.exists(),(s,d)
 assert d.resolve().is_relative_to(R.resolve()),d
 assert s.stat().st_size==int(r['bytes']) and s.stat().st_mtime_ns==int(r['mtime_ns']),s
out=[];start=time.time()
for i,r in enumerate(rows):
 s=Path(r['source']);d=Path(r['target']);d.parent.mkdir(parents=True,exist_ok=True)
 with s.open('rb') as f,d.open('xb') as g:shutil.copyfileobj(f,g,8*1024*1024)
 shutil.copystat(s,d)
 digest=sha(d);assert digest==r['sha256'],d
 out.append(dict(source=str(s),target=str(d),bytes=r['bytes'],source_sha256=r['sha256'],copied_sha256=digest,status='MATCH'))
 if i%200==0:print(i+1,'/',len(rows),flush=True)
with (R/'provenance/manifests/copied_files_sha256.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
(R/'provenance/migration_reports/copy_summary.json').write_text(json.dumps(dict(files=len(out),bytes=sum(int(r['bytes']) for r in out),seconds=time.time()-start),indent=2),encoding='utf-8')
print('COPY_COMPLETE',len(out),time.time()-start,flush=True)
