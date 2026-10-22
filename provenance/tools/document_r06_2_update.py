from pathlib import Path
import json,csv,hashlib,difflib
R=Path('E:/SH');D=R/'framework/DeepLensHSI';P=R/'provenance';v=json.loads((P/'migration_reports/R06_2_baseline_update_verification.json').read_text(encoding='utf-8'));m=v['means'];changes=[]
def edit(rel,replacements=(),prefix='',suffix=''):
 p=R/rel;old=p.read_text(encoding='utf-8');backup=P/'source_code_originals/R06_2_pre_update_docs'/rel;backup.parent.mkdir(parents=True,exist_ok=True)
 with backup.open('xb') as f:f.write(p.read_bytes())
 new=old
 for a,b in replacements:
  assert new.count(a)==1,(rel,a,new.count(a));new=new.replace(a,b)
 new=prefix+new+suffix
 p.write_text(new,encoding='utf-8')
 changes.append(dict(path=str(p),before_sha256=hashlib.sha256(old.encode()).hexdigest(),after_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),backup=str(backup),diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=rel+' (before)',tofile=rel+' (after)'))))
current=f'平均PSNR {m["psnr_db"]:.9f} dB、SSIM {m["ssim"]:.6f}、固定GT掩膜SAM {m["sam_fixed_deg"]:.9f}°、历史双有效掩膜SAM {m["sam_deg"]:.9f}°'
edit('README.md',[
 ('| DeepLensHSI 原相机与预训练网络 | 8场景重新编码、推理及评价 PASS | 平均PSNR 18.186638236 dB、SSIM 0.662075、SAM 39.223211288°；与旧R05逐场景张量和指标完全一致 |',f'| DeepLensHSI 当前R06-2通道对齐基线 | 8场景重新编码、推理及评价 PASS；网络入口RGB→BGR | {current}；与原R06-2逐场景指标最大绝对差7.63e-6 |\n| 历史R05基础对照（保留） | 原18.1866dB结果归档 | 不再作为当前默认基线；旧指标与张量保留用于解释通道顺序问题 |'),
 ('迁移日期：2026-10-20。','迁移日期：2026-10-20。已补充R06-2通道对齐基线（同日）。'),
 ('原脚本暂未提供自定义输出参数，未来新增推理轮次应先增加输出目录参数并拒绝覆盖；当前可独立检查`results/R05_validation/metrics.csv`及已有日志。','更新后5/6脚本已支持自定义输出路径并拒绝覆盖；当前默认使用R06-2 BGR约定，结果见`results/R06_2_validation/metrics.csv`。R05结果保留为历史对照。'),
 ('源码未修改；默认输出固定为`results/R05_validation`。','这是更新前的R05验证记录；更新后脚本默认输出为`results/R06_2_validation`，并支持`--output`。')],suffix=r'''

## 当前默认重建基线：R06-2

原相机仍输出物理RGB，推理前按`encoded_rgb[:, [2,1,0], :, :]`适配网络输入。开关为`configs/1_deeplens_hsi.yml`中的`network.swap_rgb_channels: true`；没有修改nafnet_hsi.pth、传感器曲线、GT或31谱通道顺序。仅此处的5/6验证入口为本次更新的主入口；原1/3训练/演示脚本保留来源版本，不要据其旧默认行为判断当前基线。

从DeepLensHSI子目录执行；下面两条命令必须选择尚未使用的新输出路径：

```powershell
Set-Location E:\SH\framework\DeepLensHSI
& $py -B 5_eval_pretrained.py --limit 8 --output results/my_r06_run
& $py -B 6_evaluate_metrics.py --input results/my_r06_run
```

`--no-swap-rb --output results/my_rgb_control`可显式回到RGB对照；不改变默认配置。评价表`sam_deg`沿用历史双有效掩膜SAM，`sam_fixed_deg`为固定GT掩膜SAM（GT有效但预测为零按90°计）。30.8194dB为8场景PSNR算术平均，不是全局MSE聚合PSNR（原R06-2约28.2027dB）。

原证据完整迁入`framework/DeepLensHSI/reports/R06-2_channel_swap/`；新验证与差异报告见`provenance/migration_reports/R06_2_baseline_update.md`。
''')
edit('framework/DeepLensHSI/MIGRATION.md',prefix=f'''# R06-2补充更新（2026-10-20，当前有效）

当前主入口为5_eval_pretrained.py和6_evaluate_metrics.py，默认网络输入BGR；{current}。8场景实跑通过，原证据已迁入reports/R06-2_channel_swap，新的结果在results/R06_2_validation。模型权重、物理RGB响应和数据未改；支持--output避免覆盖。原1/3入口保持来源行为，不作为当前通道对齐验证入口。

以下为更新前R05迁移记录，保留溯源，其“脚本未改/不支持新输出参数”描述已被本次更新取代。

''')
edit('integration/single_spiral_to_hsi/INTERFACE_PLAN.md',suffix='\n\n## R06-2输入约定补充（2026-10-20）\n\n现有nafnet_hsi.pth在验证时需要在物理RGB编码之后、模型入口之前执行[R,G,B]→[B,G,R]。新基线已在8场景验证到30.8194dB；不要将这一适配实现为交换物理传感器响应或HSI真值通道。未来单螺旋PSF接入也须显式记录这一网络输入约定，并重新验证权重适用性。N02科学门控状态仍保持原结论。\n')
edit('provenance/audit/dependency_graph.md',suffix='\n\n## R06-2当前推理路径补充\n\n5_eval_pretrained读取network.swap_rgb_channels，在相机物理RGB之后、NAFNet之前按[2,1,0]重排；6_evaluate_metrics默认读取results/R06_2_validation并同时记录两种SAM。原R06-2报告、脚本和14项证据原样复制；增量清单见R06_2_update_candidate_dry_run.csv与R06_2_update_copied_sha256.csv。其余光学与数据依赖不变。\n')
report=f'''# R06-2当前重建基线更新验收

日期：2026-10-20。状态：**PASS**。用户指出旧迁移只选择了R05基础版本，本次将R06-2作为当前默认推理基线。

## 实测结果

{current}。8/8场景PSNR优于旧R05，8场景平均PSNR提升约12.6328dB。30.8194dB是逐场景dB的算术平均；原受控实验的全局MSE聚合PSNR是28.2027dB，应区分统计方式。

原R06-2历史结果：PSNR30.819419860840dB、SSIM0.8498、固定GT掩膜SAM21.931971549988°、历史双有效掩膜SAM17.079045772552°。本次各场景各指标最大绝对差{v['max_absolute_metric_difference']:.17g}，均小于事先设定1e-4容差；PSNR最大差3.8146973e-6dB。差异处在GPU/CPU归约和no_grad/inference_mode路径的浮点舍入量级；没有为通过而调宽容差。

## 实现与来源

- 原reports/R06-2_channel_swap目录14个文件共5347222字节先形成干运行清单，再复制并逐项验证SHA相同。包含报告、脚本、图、指标、日志和evidence；历史文档路径不替换。
- 改动仅新工作区的配置、5_eval_pretrained.py与6_evaluate_metrics.py，保存适配前原始字节及完整diff。
- 配置network.swap_rgb_channels=true；5在model前将encoded_rgb按[2,1,0]排列。权重文件不变，物理RGB和GT不变。默认新输出results/R06_2_validation；支持--output、--swap-rb/--no-swap-rb。5拒绝已有输出目录；6支持--input/--output并拒绝已有CSV。
- 6保留历史sam_deg，新增sam_fixed_deg；固定GT掩膜中零预测按90°计。预训练checkpoint SHA：`{v['weight_sha256']}`。
- 原1/3脚本保留来源版本；当前通道对齐主入口为5/6，不涉及重训。

## 执行与独立性

在E:/SH/framework/DeepLensHSI以Python3.10.22、torch2.5.1+cu121、RTX4060运行：

```powershell
& $py -B 5_eval_pretrained.py --limit 8
& $py -B 6_evaluate_metrics.py
```

两命令由record_run.py设置旧源路径屏蔽后执行，8场景均成功。对应日志和耗时为R06_2_updated_inference.log/command.json及R06_2_updated_metrics.log/command.json。source_R06_2_update_verification为只读源完整性检查，刻意不启用路径屏蔽，与独立推理证据分开。

输出保护另测默认BGR推理、--no-swap-rb旧RGB路由及评价CSV拒绝覆盖，检查现有文件SHA未改变，详见R06_2_output_protection.json。

## 文件与文档

旧R05结果、旧报告与迁移计数作为历史快照保留。主README切换到R06-2当前基线，最终迁移报告顶部增加本次补充；原报告全文及修改前文档均保留。没有删除操作。

新增/修改清单：provenance/manifests/R06_2_update_candidate_dry_run.csv、R06_2_update_copied_sha256.csv；代码差异见provenance/audit/R06_2_code_adaptations.patch。完整8场景数值差异、模型与数据保护结果见R06_2_baseline_update_verification.json。

## 源目录保护

本轮源B所有1344项文件的SHA-256、size、mtime_ns、文件清单和Git HEAD/status/暂存/未暂存diff/remote前后完全一致。290项已迁入的模型、光学、传感器、样例和历史参考也逐项SHA核对通过。旧源A本轮未操作；其先前完整保护证明仍保留。本次所有写入均位于E:/SH。

N02的G2/G3仍FAIL、R2全局结论未定；本次仅更新原DeepLens相机的重建基线，不改变新单孔径PSF尚未接入的状态。
'''
with (P/'migration_reports/R06_2_baseline_update.md').open('x',encoding='utf-8') as f:f.write(report)
edit('provenance/migration_reports/final_report.md',prefix=f'''# 当前补充：R06-2通道对齐基线（2026-10-20）

**当前DeepLensHSI默认基线已更新，8场景独立实跑PASS：{current}。** 网络入口RGB→BGR，预训练权重和物理传感器不改；旧R05约18.18dB为基础历史对照。

新验收详见[R06_2_baseline_update.md](R06_2_baseline_update.md)，原R06-2证据在framework/DeepLensHSI/reports/R06-2_channel_swap。源B完整1344文件及Git状态前后不变。原808项复制计数与target_current_sha256.csv是更新前快照；增量14项原证据及新代码状态见R06_2增量清单和target_current_sha256_R06_2.csv。默认推理/评价已支持新输出路径并拒绝覆盖，旧文中的相应待办已解决。

N02原限制仍有效。以下原始迁移报告全文保留溯源，其中R05及“5/6脚本未改”等表述为更新前状态。

''')
with (P/'audit/R06_2_document_adaptations.json').open('x',encoding='utf-8') as f:json.dump(changes,f,ensure_ascii=False,indent=2)
# 更新后的当前状态独立落盘；之前清单保留为历史快照。
rows=list(csv.DictReader((P/'manifests/target_current_sha256.csv').open(encoding='utf-8-sig')))
newcopies=list(csv.DictReader((P/'manifests/R06_2_update_copied_sha256.csv').open(encoding='utf-8-sig')))
for row in rows:
 p=Path(row['target']);row['current_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();row['bytes']=p.stat().st_size
 row['status']='SOURCE_MATCH' if row['current_sha256']==row['source_sha256'] else 'ADAPTED_RECORDED'
for row in newcopies:rows.append(dict(target=row['target'],current_sha256=row['copied_sha256'],source_sha256=row['sha256'],status='SOURCE_MATCH',bytes=row['bytes']))
with (P/'manifests/target_current_sha256_R06_2.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('R06_2 DOCUMENTATION_UPDATED; current copy entries',len(rows))
