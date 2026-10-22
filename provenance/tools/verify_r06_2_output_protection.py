import subprocess,sys,json,hashlib
from pathlib import Path
D=Path('E:/SH/framework/DeepLensHSI');rows=[]
for args,path in [(['5_eval_pretrained.py','--limit','8'],D/'results/R06_2_validation/photo_and_face_ms/spectra.pt'),(['5_eval_pretrained.py','--no-swap-rb'],D/'results/R05_validation/photo_and_face_ms/spectra.pt'),(['6_evaluate_metrics.py'],D/'results/R06_2_validation/metrics.csv')]:
 before=hashlib.sha256(path.read_bytes()).hexdigest();p=subprocess.run([sys.executable,'-B']+args,cwd=D,capture_output=True,encoding='utf-8');assert p.returncode!=0 and 'FileExistsError' in p.stderr,(args,p.stderr)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==before
 rows.append(dict(args=args,existing_output_rejected=True,existing_file_sha256_unchanged=True))
with Path('E:/SH/provenance/migration_reports/R06_2_output_protection.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',checks=rows),f,ensure_ascii=False,indent=2)
print('OUTPUT_PROTECTION_PASS',len(rows))
