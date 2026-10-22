"""受前置门禁约束的结构选择；禁止数值不收敛时继续扩展。"""
import sys
sys.dont_write_bytecode=True
import json
from pathlib import Path
from optics import *
from audit import write,textfile
from evaluate import csvwrite,evaluate


def select(out,cfg,numerics):
    if numerics!='PASS':
        states={g:dict(status='INCONCLUSIVE',execution='NOT_TESTED',reason='G3关键数值门失败，依据任务书停止条件停止结构扫描/优化/双孔径与重建') for g in ['G4','G5','G6','G7','G8']}
        write(out/'downstream_gates.json',states)
        for gate,title in [('gate4_ablation.md','硬/软环带'),('gate5_nf_mechanism.md','菲涅尔数扫描'),
                           ('gate6_optimizer_ablation.md','低维优化'),('gate7_single_aperture_identifiability.md','单孔径谱辨识'),
                           ('gate7_dual_aperture_complementarity.md','双孔径互补性'),('gate8_reconstruction.md','场景重建')]:
            textfile(out/gate,f'# {title}\n\nNOT_TESTED。前置G3-Numerics失败，按任务书第14节优先停止条件不扩展。已有PSF Gram仅形态字典诊断，不代表未知场景可辨识性或重建。\n')
        textfile(out/'completion_summary_batch3.md','# 批次3/4门禁停止\n\nG4–G8未执行（INCONCLUSIVE / NOT_TESTED），没有优化、双孔径或重建结果。先解决数值收敛和425nm冻结定位失败。\n')
        return
    # 数值门通过时，先完成同几何硬/软消融和有限R诊断；不自动触发优化。
    runner=module('n02_runner_selection',Path(__file__).with_name('run.py'))
    make_folder,acquire_case,STANDARD=(getattr(runner,n) for n in ['make_folder','acquire_case','STANDARD'])
    rows=[]
    for sigma in [.025,.04,.05,.065,.08]:
        for continuous in ([False,True] if sigma==.05 else [False]):
            name=f'soft_sigma{sigma:g}_{"continuous" if continuous else "Q10"}'
            cc=dict(cfg,candidate_id=name);d=design(cc,soft_sigma=sigma,continuous=continuous)
            folder=make_folder(out,name,cc,d,continuous)
            for w in STANDARD:acquire_case(out,folder,d,d['height'],w,cc)
            rr,ll,ss,ii=evaluate(folder,cc,STANDARD)
            rows.append(dict(sigma_v=sigma,continuous=continuous,low_U_fraction=d['soft_low_amplitude_fraction'],**ss))
    csvwrite(out/'gate4_hard_vs_soft.csv',rows)
    write(out/'gate4_selected_architecture.json',dict(selected='hard',reason='软结构须全硬门无退化且核心改进超数值误差；未独立证明前冻结硬结构'))
    scans=[]
    for radius in [400.,450.,500.,550.,600.,650.]:
        if radius==500.:
            ss=json.loads((out/'B2/standard_summary.json').read_text(encoding='utf-8'))
        else:
            cc=dict(cfg,R_um=radius,candidate_id=f'R{radius:g}')
            d=design(cc);folder=make_folder(out,cc['candidate_id'],cc,d)
            for w in STANDARD:acquire_case(out,folder,d,d['height'],w,cc)
            rr,ll,ss,ii=evaluate(folder,cc,STANDARD)
        scans.append(dict(R_um=radius,NF=radius**2/(2*.5461*20000),area_relative_to_B2=(radius/500)**2,**ss))
    csvwrite(out/'gate5_geometry_sweep.csv',scans)
    csvwrite(out/'gate5_pareto.csv',[r for r in scans if not any(
        q['n02_valid']>=r['n02_valid'] and q['min_main_incident_fraction']>=r['min_main_incident_fraction'] and q['min_outside_ratio']>=r['min_outside_ratio'] and
        (q['n02_valid']>r['n02_valid'] or q['min_main_incident_fraction']>r['min_main_incident_fraction'] or q['min_outside_ratio']>r['min_outside_ratio']) for q in scans)])
    write(out/'downstream_gates.json',dict(G4=dict(status='INCONCLUSIVE',execution='SIMULATED',reason='完整数据见CSV，软结构优势未独立认证'),
       G5=dict(status='INCONCLUSIVE',execution='SIMULATED',reason='有限R扫描；尚无逐候选蓝端/收敛验证'),
       **{g:dict(status='INCONCLUSIVE',execution='NOT_TESTED',reason='蓝端硬门未通过或尚无可信选型，不进入后续') for g in ['G6','G7','G8']}))
