import os,json,csv,hashlib,subprocess,time
from pathlib import Path
R=Path('E:/SH');os.environ['GIT_OPTIONAL_LOCKS']='0'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
start=time.time();reports={}
for label,root in [('A',Path('E:/SpiralDOE_HSI/n00_run_20261009')),('B',Path('E:/DeepLensHSI'))]:
 before=json.loads((R/f'provenance/manifests/source_{label}_inventory.json').read_text(encoding='utf-8'));lookup={r['relative']:r for r in before};changes=[];seen=set()
 for base,dirs,files in os.walk(root,followlinks=False):
  for name in files:
   p=Path(base)/name;rel=p.relative_to(root).as_posix();seen.add(rel);s=p.stat();prior=lookup.get(rel)
   if prior is None:changes.append(dict(path=rel,reason='added'));continue
   digest=sha(p)
   if (s.st_size,s.st_mtime_ns,digest)!=(prior['bytes'],prior['mtime_ns'],prior['sha256']):changes.append(dict(path=rel,reason='content_or_metadata_changed'))
 for rel in lookup.keys()-seen:changes.append(dict(path=rel,reason='missing'))
 parts=[]
 for args in [['rev-parse','HEAD'],['status','--porcelain=v1','--untracked-files=all'],['remote','-v'],['config','--local','--list'],['diff','--binary'],['diff','--cached','--binary']]:
  p=subprocess.run(['git','--no-optional-locks','-C',str(root)]+args,capture_output=True)
  parts.append('$ git '+' '.join(args)+'\n'+p.stdout.decode('utf-8',errors='replace')+p.stderr.decode('utf-8',errors='replace'))
 text='\n'.join(parts)
 with (R/f'provenance/source_git_state/{label}_after.txt').open('x',encoding='utf-8') as f:f.write(text)
 git_equal=text==(R/f'provenance/source_git_state/{label}.txt').read_text(encoding='utf-8')
 reports[label]=dict(files=len(seen),bytes=sum(r['bytes'] for r in before),all_file_sha256_size_mtime_equal=not changes,git_head_status_index_worktree_config_remote_equal=git_equal,changes=changes)
 print(label,json.dumps(reports[label],ensure_ascii=False),flush=True)
with (R/'provenance/migration_reports/source_preservation.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS' if all(not r['changes'] and r['git_head_status_index_worktree_config_remote_equal'] for r in reports.values()) else 'FAIL',sources=reports,seconds=time.time()-start),f,ensure_ascii=False,indent=2)
