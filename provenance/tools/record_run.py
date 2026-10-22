import sys,subprocess,time,json,os
from pathlib import Path
R=Path('E:/SH');label=sys.argv[1];cwd=sys.argv[2];cmd=sys.argv[3:]
os.environ.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(R/'provenance/runtime_cache/matplotlib'),TORCH_HOME=str(R/'provenance/runtime_cache/torch'),TEMP=str(R/'provenance/runtime_cache/temp'),TMP=str(R/'provenance/runtime_cache/temp'),GIT_OPTIONAL_LOCKS='0')
if not label.startswith('source_'):os.environ['PYTHONPATH']=str(R/'provenance/guard')
start=time.time();p=subprocess.run(cmd,cwd=cwd,capture_output=True,encoding='utf-8',errors='replace');elapsed=time.time()-start
report=R/'provenance/migration_reports'
with (report/(label+'.log')).open('x',encoding='utf-8') as f:f.write(p.stdout+'\n'+p.stderr)
with (report/(label+'_command.json')).open('x',encoding='utf-8') as f:json.dump(dict(command=cmd,cwd=cwd,returncode=p.returncode,seconds=elapsed,source_guard=not label.startswith('source_')),f,ensure_ascii=False,indent=2)
print(p.stdout[-5000:]);print(p.stderr[-4000:]);print(label,'EXIT',p.returncode,'seconds',elapsed,flush=True)
sys.exit(p.returncode)
