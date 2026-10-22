import json,os,subprocess
from pathlib import Path
r=Path('E:/SH');os.environ['GIT_OPTIONAL_LOCKS']='0';changes=[]
for lab in ['A','B']:
 rows=json.loads((r/f'provenance/manifests/source_{lab}_inventory.json').read_text(encoding='utf-8'))
 for row in rows:
  p=Path(row['source']);s=p.stat()
  if s.st_size!=row['bytes'] or s.st_mtime_ns!=row['mtime_ns']:changes.append(str(p))
 root=Path(rows[0]['source'])
 root=Path('E:/SpiralDOE_HSI/n00_run_20261009') if lab=='A' else Path('E:/DeepLensHSI')
 parts=[]
 for args in [['rev-parse','HEAD'],['status','--porcelain=v1','--untracked-files=all'],['remote','-v'],['config','--local','--list'],['diff','--binary'],['diff','--cached','--binary']]:
  p=subprocess.run(['git','--no-optional-locks','-C',str(root)]+args,capture_output=True)
  parts.append('$ git '+' '.join(args)+'\n'+p.stdout.decode('utf-8',errors='replace')+p.stderr.decode('utf-8',errors='replace'))
 assert '\n'.join(parts)==(r/f'provenance/source_git_state/{lab}.txt').read_text(encoding='utf-8'),lab
assert not changes,changes
(r/'provenance/migration_reports/M00_dry_run.md').write_text('# M00 干运行核验\n\n两个源共8854文件，23723109156字节；逐文件大小、mtime_ns、SHA-256已记录，包括Git元数据。\n精选805个复制项，1309302726字节；目标冲突0；空闲空间80693288960字节。\n未发现重解析链接；复制前源文件size/mtime及Git HEAD、状态、暂存/未暂存差异完全一致。\n\n分类及逐项理由见 candidate_dry_run.csv；B2保留标准25波长、420–430nm逐nm与546.1nm及原收敛测试输入。\n保留8个最小旧源码文件至vendor_compat，不搬迁N01实验结果。历史整包审计依赖未选入的旧变体，不能作为独立入口；迁移采用固定输入验证入口。\n',encoding='utf-8')
print('M00 source state unchanged')
