import os,json,hashlib,csv,ast,subprocess
from pathlib import Path
R=Path('E:/SH');N=R/'optics/n02_single_spiral';A=Path('E:/SpiralDOE_HSI/n00_run_20261009')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs=json.loads((N/'results/n02_1c_r2/n02_1cr2_20261020_02/input_hashes.json').read_text(encoding='utf-8'))
selected=list(csv.DictReader((R/'provenance/manifests/selected_files.csv').open(encoding='utf-8-sig')))
lookup={}
for row in selected:lookup.setdefault(row['source'].replace('\\','/').lower(),[]).append(row)
# 保存发生路径适配的源码原始字节，供历史输入清单逐项核验。
newrows=[]
for name in ['experiments/n02/optics.py','experiments/n02_1c_r/p0b_common.py']:
 source=A/name;target=R/'provenance/source_code_originals'/name
 row=lookup[str(source).replace('\\','/').lower()][0]
 assert sha(source)==row['sha256'];target.parent.mkdir(parents=True,exist_ok=True)
 with target.open('xb') as f:f.write(source.read_bytes())
 newrows.append(dict(source=str(source),target=str(target),sha256=sha(target),reason='适配前原始源码字节，用于历史输入SHA验证'))
task=N/'results/n02_1c_r2/n02_1cr2_20261020_02/task_original.md';data=task.read_text(encoding='utf-8').encode('utf-8');tasktarget=R/'provenance/source_tasks/R2_original_LF.md';tasktarget.parent.mkdir(parents=True,exist_ok=True)
assert hashlib.sha256(data).hexdigest()==next(iter(inputs.values()))
with tasktarget.open('xb') as f:f.write(data)
newrows.append(dict(source=str(task),target=str(tasktarget),sha256=sha(tasktarget),reason='REGENERATE：从任务书快照恢复LF字节；与原输入完整SHA匹配'))
resolved=[]
for original,digest in inputs.items():
 candidates=lookup.get(original.lower(),[])
 targets=[Path(r['target']) for r in candidates]
 if original.startswith('C:'):targets.insert(0,tasktarget)
 else:
  rel=Path(original).relative_to(A).as_posix();saved=R/'provenance/source_code_originals'/rel
  if saved.exists():targets.insert(0,saved)
 found=next((p for p in targets if p.is_file() and sha(p)==digest),None)
 resolved.append(dict(original_path=original,expected_sha256=digest,resolved_path=str(found) if found else '',status='MATCH' if found else 'BLOCKED'))
assert all(r['status']=='MATCH' for r in resolved),[r for r in resolved if r['status']!='MATCH']
with (R/'provenance/manifests/supplemental_evidence.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(newrows[0]));w.writeheader();w.writerows(newrows)
with (R/'provenance/audit/R2_input_resolution.json').open('x',encoding='utf-8') as f:json.dump(resolved,f,ensure_ascii=False,indent=2)
src=json.loads((R/'provenance/migration_reports/source_N02_frozen.json').read_text(encoding='utf-8'));dst=json.loads((R/'provenance/migration_reports/N02_frozen.json').read_text(encoding='utf-8'))
assert src['probe']==dst['probe'] and src['standard_records']==dst['standard_records']
with (R/'provenance/migration_reports/N02_parity.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',same_fixed_height_phase_field=True,same_complex128_small_ASM=True,same_negative_height_error=True,all_25_metrics_records_exact_equal=True,metric_absolute_error_max=0,complete_R2_input_hashes_resolved=len(resolved)),f,indent=2)
# 记录源码级导入及文件读取调用；动态链条另在Markdown解释。
graph=[]
for base in [N/'experiments',N/'vendor_compat/experiments']:
 for p in base.rglob('*.py'):
  tree=ast.parse(p.read_text(encoding='utf-8'))
  for node in ast.walk(tree):
   if isinstance(node,(ast.Import,ast.ImportFrom)):
    graph.append(dict(file=str(p.relative_to(N)),line=node.lineno,kind='import',expression=ast.unparse(node)))
   elif isinstance(node,ast.Call) and any(x in ast.unparse(node.func) for x in ['load','read','open','module','sha','spec_from_file_location']):
    graph.append(dict(file=str(p.relative_to(N)),line=node.lineno,kind='file_or_dynamic_call',expression=ast.unparse(node)[:1600]))
with (R/'provenance/audit/dependency_graph_details.json').open('x',encoding='utf-8') as f:json.dump(graph,f,ensure_ascii=False,indent=2)
print('R2 INPUTS MATCH',len(resolved),'PARITY EXACT; AST edges',len(graph))
