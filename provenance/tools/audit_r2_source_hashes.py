import sys,os,json,hashlib,csv
from pathlib import Path
R=Path('E:/SH');N=R/'optics/n02_single_spiral';m=json.loads((N/'results/n02_1c_r2/n02_1cr2_20261020_02/manifest.json').read_text(encoding='utf-8'));rows=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for rel,digest in m['source_hashes'].items():
 p=N/rel;actual=sha(p);status='MATCH' if actual==digest else 'ADAPTED'
 if status=='ADAPTED':
  old=Path('E:/SpiralDOE_HSI/n00_run_20261009')/rel
  assert sha(old)==digest,(rel,'unexpected original source drift')
  save=R/'provenance/source_code_originals'/rel;save.parent.mkdir(parents=True,exist_ok=True)
  if not save.exists():
   with save.open('xb') as f:f.write(old.read_bytes())
  assert sha(save)==digest
  rows.append(dict(relative=rel,status='MATCH_ORIGINAL_WITH_RECORDED_PATH_ADAPTATION',archived_original=str(save),expected_sha256=digest,adapted_sha256=actual))
 else:rows.append(dict(relative=rel,status=status,expected_sha256=digest))
with (R/'provenance/audit/R2_source_resolution.json').open('x',encoding='utf-8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
print('R2 sources resolved',len(rows))
