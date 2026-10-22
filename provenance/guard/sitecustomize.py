"""迁移验收时屏蔽旧源目录的文件访问；子进程通过PYTHONPATH继承。"""
import os,sys
_BLOCKED=('e:/spiraldoe_hsi','e:/deeplenshsi','c:/users/李咏晨/downloads')
def _migration_guard(event,args):
 if event in ('open','os.listdir','os.scandir','os.chdir') and args:
  p=args[0]
  if isinstance(p,(str,bytes,os.PathLike)):
   s=os.path.abspath(os.fsdecode(p)).replace('\\','/').lower()
   if any(s==f or s.startswith(f+'/') for f in _BLOCKED):raise PermissionError('迁移隔离验证拒绝源路径: '+s)
sys.addaudithook(_migration_guard)
os.environ['SH_SOURCE_GUARD']='1'
