import os
from pathlib import Path
assert os.environ.get('SH_SOURCE_GUARD')=='1'
count=0
for p in ['E:/DeepLensHSI/README.md','E:/SpiralDOE_HSI/n00_run_20261009/README.md']:
 try:Path(p).read_bytes()
 except PermissionError:count+=1
assert count==2
print('SOURCE_GUARD_PASS',count)
