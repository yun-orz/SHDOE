import os, sys, json, subprocess, hashlib, csv, shutil, time
from pathlib import Path
ROOT=Path('E:/SH')
A=Path('E:/SpiralDOE_HSI/n00_run_20261009'); B=Path('E:/DeepLensHSI')
os.environ['GIT_OPTIONAL_LOCKS']='0'
def write(p,s):
 p=ROOT/p; p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(s)
def git(root,args):
 p=subprocess.run(['git','--no-optional-locks','-C',str(root)]+args,capture_output=True)
 return p.stdout.decode('utf-8',errors='replace')+p.stderr.decode('utf-8',errors='replace')
def snapshot(label,root,suffix=''):
 out=[]
 for args in [['rev-parse','HEAD'],['status','--porcelain=v1','--untracked-files=all'],['remote','-v'],['config','--local','--list'],['diff','--binary'],['diff','--cached','--binary']]:
  out.append('$ git '+' '.join(args)+'\n'+git(root,args))
 text='\n'.join(out);write(Path('provenance/source_git_state')/(label+suffix+'.txt'),text);return text
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def inventory(root):
 rows=[];links=[]
 for base,dirs,files in os.walk(root,followlinks=False):
  for name in list(dirs):
   p=Path(base)/name
   if p.is_symlink() or (p.stat(follow_symlinks=False).st_file_attributes & 0x400):
    links.append(str(p));dirs.remove(name)
  for name in files:
   p=Path(base)/name;s=p.stat(follow_symlinks=False)
   if s.st_file_attributes & 0x400:links.append(str(p));continue
   rel=p.relative_to(root).as_posix()
   rows.append(dict(source=str(p),relative=rel,bytes=s.st_size,mtime_ns=s.st_mtime_ns,sha256=sha(p)))
 return rows,links
start=time.time();data={}
for label,root in [('A',A),('B',B)]:
 snapshot(label,root)
 print('Git snapshot',label,flush=True)
 rows,links=inventory(root);data[label]=rows
 write(Path('provenance/manifests')/('source_'+label+'_inventory.json'),json.dumps(rows,ensure_ascii=False,indent=2))
 write(Path('provenance/audit')/('source_'+label+'_links.json'),json.dumps(links,ensure_ascii=False,indent=2))
 print(label,len(rows),sum(r['bytes'] for r in rows),'bytes; links',links,flush=True)
write(Path('provenance/manifests/source_totals.json'),json.dumps({k:dict(files=len(v),bytes=sum(r['bytes'] for r in v)) for k,v in data.items()},indent=2))
print('free',shutil.disk_usage(ROOT).free,'elapsed',time.time()-start,flush=True)
