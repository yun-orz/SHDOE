import os,json,hashlib,csv,subprocess,shutil,difflib
from pathlib import Path
S=Path('E:/DeepLensHSI');R=Path('E:/SH');D=R/'framework/DeepLensHSI';P=R/'provenance';os.environ['GIT_OPTIONAL_LOCKS']='0'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def snapshot():
 rows=[]
 for b,dirs,files in os.walk(S):
  for n in files:
   p=Path(b)/n;s=p.stat();rows.append(dict(path=p.relative_to(S).as_posix(),bytes=s.st_size,mtime_ns=s.st_mtime_ns,sha256=sha(p)))
 commands={}
 for args in [['rev-parse','HEAD'],['status','--porcelain=v1','--untracked-files=all'],['diff','--binary'],['diff','--cached','--binary'],['remote','-v']]:
  out=subprocess.run(['git','--no-optional-locks','-C',str(S)]+args,capture_output=True);commands[' '.join(args)]=dict(returncode=out.returncode,stdout=out.stdout.decode('utf-8',errors='replace'),stderr=out.stderr.decode('utf-8',errors='replace'))
 return dict(files=rows,git=commands)
state=snapshot()
with (P/'source_git_state/B_R06_2_update_before.json').open('x',encoding='utf-8') as f:json.dump(state,f,ensure_ascii=False,indent=2)
lookup={r['path']:r for r in state['files']};selected=[]
for rel,row in lookup.items():
 if rel.startswith('reports/R06-2_channel_swap/') and '__pycache__' not in Path(rel).parts and not rel.endswith('.pyc'):
  selected.append(dict(source=str(S/rel),target=str(D/rel),**row,reason='R06-2原始报告、受控对照脚本、逐场景指标、图像及来源证据'))
assert selected
for row in selected:assert not Path(row['target']).exists(),row['target']
with (P/'manifests/R06_2_update_candidate_dry_run.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
assert shutil.disk_usage(R).free>sum(r['bytes'] for r in selected)*2
for row in selected:
 source=Path(row['source']);target=Path(row['target']);target.parent.mkdir(parents=True,exist_ok=True)
 with source.open('rb') as f,target.open('xb') as g:shutil.copyfileobj(f,g)
 shutil.copystat(source,target);assert sha(target)==row['sha256'];row['copied_sha256']=sha(target)
with (P/'manifests/R06_2_update_copied_sha256.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
# 保存当前SH文件原始字节；改动只涉及本次推理适配和可选择的新输出目录。
changes=[]
def edit(rel,edits):
 p=D/rel;original=p.read_bytes();backup=P/'source_code_originals/R06_2_pre_update'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
 with backup.open('xb') as f:f.write(original)
 text=original.decode('utf-8');oldtext=text
 for old,new in edits:
  assert text.count(old)==1,(p,old,text.count(old));text=text.replace(old,new)
 p.write_text(text,encoding='utf-8',newline='')
 changes.append(dict(path=str(p),before_sha256=hashlib.sha256(original).hexdigest(),after_sha256=sha(p),backup=str(backup),diff=''.join(difflib.unified_diff(oldtext.splitlines(True),text.splitlines(True),fromfile=rel+' (before)',tofile=rel+' (after)'))))
# Windows源文件使用CRLF，替换前统一为文本换行；备份保留原始字节。
def normal_edit(rel,edits):
 p=D/rel;original=p.read_bytes();backup=P/'source_code_originals/R06_2_pre_update'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
 with backup.open('xb') as f:f.write(original)
 oldtext=p.read_text(encoding='utf-8');text=oldtext
 for old,new in edits:
  assert text.count(old)==1,(rel,old,text.count(old));text=text.replace(old,new)
 with p.open('w',encoding='utf-8',newline='\n') as f:f.write(text)
 changes.append(dict(path=str(p),before_sha256=hashlib.sha256(original).hexdigest(),after_sha256=sha(p),backup=str(backup),diff=''.join(difflib.unified_diff(oldtext.splitlines(True),text.splitlines(True),fromfile=rel+' (before)',tofile=rel+' (after)'))))
normal_edit('configs/1_deeplens_hsi.yml',[("network:\n  name: NAFNet","network:\n  # 原预训练模型使用BGR输入约定；只在网络入口交换红蓝通道。\n  swap_rgb_channels: true\n  name: NAFNet")])
normal_edit('5_eval_pretrained.py',[
 ('parser.add_argument("--limit", type=int, default=1)','parser.add_argument("--limit", type=int, default=1)\n    parser.add_argument("--output", type=Path, help="尚不存在的新输出目录")\n    parser.add_argument("--swap-rb", action=argparse.BooleanOptionalAction, default=None,\n                        help="覆盖配置中的网络输入红蓝交换开关")'),
 ('    # 2. 验证集：保持原仓库的 512×512 配置','    # 只适配网络输入，不改传感器响应、GT或预训练权重。\n    swap_rb = cfg["network"].get("swap_rgb_channels", False) if args.swap_rb is None else args.swap_rb\n    out_root = args.output or Path("results/R06_2_validation" if swap_rb else "results/R05_validation")\n    if out_root.exists():\n        raise FileExistsError(f"输出目录已存在，请指定新的 --output：{out_root}")\n    if args.limit < 1:\n        raise ValueError("--limit必须为正整数")\n    torch.manual_seed(cfg.get("seed", 42))\n    print("网络输入通道:", "BGR（R06-2）" if swap_rb else "RGB（R05对照）")\n\n    # 2. 验证集：保持原仓库的 512×512 配置'),
 ('    out_root = Path("results/R05_validation")\n    out_root.mkdir(parents=True, exist_ok=True)','    out_root.mkdir(parents=True, exist_ok=False)'),
 ('            pred = model(encoded_rgb).clamp(0, 1)','            model_input = encoded_rgb[:, [2, 1, 0], :, :] if swap_rb else encoded_rgb\n            pred = model(model_input).clamp(0, 1)'),
 ('    print("\\nR05-2 本次推理完成")','    print("\\n预训练推理完成，通道适配:", swap_rb)')])
normal_edit('6_evaluate_metrics.py',[
 ('import csv\n','import argparse\nimport csv\n'),
 ('root = Path("results/R05_validation")','parser = argparse.ArgumentParser()\nparser.add_argument("--input", type=Path, default=Path("results/R06_2_validation"))\nparser.add_argument("--output", type=Path, help="指标CSV路径，必须尚不存在")\nargs = parser.parse_args()\nroot = args.input\noutput = args.output or root / "metrics.csv"\nif output.exists():\n    raise FileExistsError(f"指标文件已存在，请指定新的 --output：{output}")'),
 ('    valid_pct = valid.float().mean() * 100\n','    valid_pct = valid.float().mean() * 100\n\n    # 固定GT掩膜作为R06-2的公平比较口径；预测零向量按90度计。\n    valid_gt = gt_norm > 1e-8\n    fixed_angles = torch.full_like(gt_norm[valid_gt], 90.0)\n    nonzero = pred_norm[valid_gt] > 1e-8\n    fixed_cos = dot[valid_gt][nonzero] / (gt_norm[valid_gt][nonzero] * pred_norm[valid_gt][nonzero])\n    fixed_angles[nonzero] = torch.rad2deg(torch.acos(fixed_cos.clamp(-1.0, 1.0)))\n    sam_fixed = fixed_angles.mean()\n'),
 ('        "sam_valid_pct": float(valid_pct),','        "sam_valid_pct": float(valid_pct),\n        "sam_fixed_deg": float(sam_fixed),\n        "sam_fixed_valid_pct": float(valid_gt.float().mean() * 100),'),
 ('for key in ["psnr_db", "ssim", "sam_deg"]:','print("sam_deg沿用历史双有效掩膜；sam_fixed_deg为固定GT掩膜")\nfor key in ["psnr_db", "ssim", "sam_deg", "sam_fixed_deg"]:'),
 ('output = root / "metrics.csv"','output.parent.mkdir(parents=True, exist_ok=True)'),
 ('with open(output, "w", newline="", encoding="utf-8-sig") as f:','with open(output, "x", newline="", encoding="utf-8-sig") as f:'),
 ('            "sam_deg", "sam_valid_pct"','            "sam_deg", "sam_valid_pct",\n            "sam_fixed_deg", "sam_fixed_valid_pct"'),
 ('print("R05-3 完成")','print("指标评价完成")')])
with (P/'audit/R06_2_code_adaptations.json').open('x',encoding='utf-8') as f:json.dump(changes,f,ensure_ascii=False,indent=2)
with (P/'audit/R06_2_code_adaptations.patch').open('x',encoding='utf-8') as f:f.write('\n'.join(c['diff'] for c in changes))
print('R06-2 COPIED',len(selected),sum(r['bytes'] for r in selected),'bytes; ADAPTED',len(changes),'files')
