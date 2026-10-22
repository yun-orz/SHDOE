import json,hashlib,difflib,csv
from pathlib import Path
R=Path('E:/SH');N=R/'optics/n02_single_spiral';F=R/'optics/n00_forward';D=R/'framework/DeepLensHSI'
changes=[]
def edit(p,old,new):
 text=p.read_text(encoding='utf-8');assert text.count(old)==1,(p,old,text.count(old));updated=text.replace(old,new)
 p.write_text(updated,encoding='utf-8')
 changes.append(dict(path=str(p),before_sha256=hashlib.sha256(text.encode()).hexdigest(),after_sha256=hashlib.sha256(updated.encode()).hexdigest(),diff=''.join(difflib.unified_diff(text.splitlines(True),updated.splitlines(True),fromfile=str(p)+' (copied)',tofile=str(p)+' (adapted)'))))
def create(p,s):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(s)
head=(R/'provenance/source_git_state/A.txt').read_text(encoding='utf-8').splitlines()[1]
create(F/'source_snapshot.json',json.dumps(dict(source_head=head,source='A',git_state='../../provenance/source_git_state/A.txt'),ensure_ascii=False,indent=2))
edit(F/'scripts/run_n00_psf.py',"subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()","json.loads((ROOT/'source_snapshot.json').read_text(encoding='utf-8'))['source_head']")
edit(N/'experiments/n02/optics.py',"ROOT/'experiments/N01_3A_G2_f2_q6_13wave/support.py'","ROOT/'vendor_compat/experiments/N01_3A_G2_f2_q6_13wave/support.py'")
for branch,file,run in [('n02_1c_r','p0b_common.py','n02_1cr_20261020_01'),('n02_1c_r2','r2_common.py','n02_1cr2_20261020_02')]:
 p=N/'experiments'/branch/file
 text=p.read_text(encoding='utf-8');line=next(x for x in text.splitlines() if x.startswith('TASK=Path('))
 edit(p,line,f"TASK=ROOT/'results/{branch}/{run}/task_original.md'")
# 迁移的历史快照工具显式禁用，避免误操作历史证据或访问旧源目录。
p=F/'scripts/snapshot_reference.py'
edit(p,"REF = Path('E:/DeepLensHSI')","REF = ROOT.parents[1]/'framework/DeepLensHSI'")
edit(p,'def snapshot():','def snapshot():\n    raise RuntimeError("历史快照工具已归档；请使用 provenance/tools 中的迁移审计入口，避免覆盖冻结证据。")')
create(R/'provenance/audit/code_adaptations.json',json.dumps(changes,ensure_ascii=False,indent=2))
create(R/'provenance/audit/code_adaptations.patch','\n'.join(c['diff'] for c in changes))
print('adapted',len(changes),'small replacements; no physics changes')
