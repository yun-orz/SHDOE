"""交付复核：独立视场外能量、统计完整性、原始哈希及补充诊断图。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sampling import centered_grid
from forward import ROOT,load,MODELS
from analysis import save_csv,NOTICE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output.resolve()
    if (out/'delivery_qa.json').exists():raise FileExistsError('拒绝覆盖交付复核产物')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    config=json.loads((out/'run_config.json').read_text(encoding='utf-8'))
    hashes=json.loads((out/'input_manifest.json').read_text(encoding='utf-8'))
    artifacts=json.loads((out/'artifact_manifest.json').read_text(encoding='utf-8'))
    changed=[p for p,d in hashes.items() if digest(ROOT/p)!=d['sha256']]
    bad=[p for p,h in artifacts.items() if digest(out/p)!=h]
    if changed or bad:raise RuntimeError(f'哈希保护失败：{changed}, {bad}')
    rows=list(csv.DictReader((out/'metrics.csv').open(encoding='utf-8',newline='')))
    sums=list(csv.DictReader((out/'summary_metrics.csv').open(encoding='utf-8',newline='')))
    matrices=json.loads((out/'matrices_9band.json').read_text(encoding='utf-8'))
    tests=json.loads((out/'tests.json').read_text(encoding='utf-8'))
    record=json.loads((out/'logs/run_record.json').read_text(encoding='utf-8'))
    if len(rows)!=record['full_solves'] or len(set(r['sample_id'] for r in rows))!=len(rows):raise RuntimeError('重复或缺失样本')
    # 通过未覆盖几何权重独立计算outside，不用total-inside定义outside来伪造守恒。
    fine,_,_,_,_,pitch=load(ROOT);_,_,w=centered_grid(512,pitch)
    coverage=np.asarray(w.sum(axis=0)).ravel()
    outside_weight=1-coverage[:,None]*coverage[None,:]
    outside_results=[]
    energy=list(csv.DictReader((out/'sampling_energy_check.csv').open(encoding='utf-8',newline='')))
    for name,cube in fine.items():
        for band,h in enumerate(cube):
            outside=float(np.sum(h*outside_weight))
            erow=next(r for r in energy if r['model']==name and float(r['wavelength_nm'])==config['wavelengths_nm'][band])
            inside=float(erow['detector_sum']);total=float(h.sum())
            error=abs(inside+outside-total)/total
            if error>1e-10 or outside < -1e-12:raise RuntimeError('独立面积守恒不通过')
            outside_results.append(dict(model=name,wavelength_nm=config['wavelengths_nm'][band],
                                        independently_integrated_outside=outside,detector_sum=inside,relative_conservation_error=error))
    save_csv(out/'independent_energy_verification.csv',outside_results)
    qerr=max(abs(float(r['actual_SNR_db'])-float(r['target_SNR_db'])) for r in rows if r['protocol'] in ['Q','mismatch_Q40'])
    if qerr>.3:raise RuntimeError('实际SNR不匹配')
    if any(r['solver_status']!='SUCCESS' for r in rows):raise RuntimeError('存在失败求解')
    pgroup={}
    for r in rows:
        if r['protocol']=='P':
            key=(r['shape_mode'],r['spectrum'],r['seed'],r['P_in'],r['read_sigma_e'])
            pgroup.setdefault(key,[]).append(float(r['expected_electrons']))
    pdiff=max((max(v)-min(v))/max(v) for v in pgroup.values())
    if any(len(v)!=3 for v in pgroup.values()) or pdiff>1e-12:raise RuntimeError('P三模型预算不完整或不一致')
    ratios=list(csv.DictReader((out/'mismatch_ratios.csv').open(encoding='utf-8',newline='')))
    # 补充SAM失配曲线与25带专用图，避免通用9带绘图模板文字误导。
    families=['common_shift_x','common_shift_y','chromatic_shift','gaussian_blur','rgb_gain']
    fig,axes=plt.subplots(1,5,figsize=(17,4.7))
    for ax,family in zip(axes,families):
        for protocol,style in [('mismatch_noiseless','-o'),('mismatch_Q40','--s')]:
            subset=sorted([r for r in sums if r['phase']=='full' and r['protocol']==protocol and r['perturbation_type']==family and r['reconstruction']=='M1_nominal'],key=lambda r:float(r['perturbation_level']))
            ax.semilogy([float(r['perturbation_level']) for r in subset],[max(float(r['SAM_deg_mean']),1e-10) for r in subset],style,label=protocol,ms=3)
        ax.set(title=family,xlabel='pixel or relative gain',ylabel='Mean SAM (deg)');ax.grid(alpha=.2);ax.legend(fontsize=6)
    fig.suptitle('B2 true-only mismatch, nominal NNLS; 9 bands 420–660nm/30nm; detector pitch 2.739786856um; shape_only',fontsize=10)
    fig.text(.5,.015,NOTICE,ha='center',fontsize=7);fig.tight_layout(rect=(0,.06,1,.92))
    fig.savefig(out/'figures/mismatch_sam_log.png',dpi=150);plt.close(fig)
    d25=json.loads((out/'matrices_25band_diagnostic.json').read_text(encoding='utf-8'))
    fig,ax=plt.subplots(figsize=(8,4.8))
    for label,d in [('9 native bands / 30nm',matrices['shape_only/'+MODELS[2]]),('25 native bands / 10nm — NO RECONSTRUCTION',d25)]:
        sv=np.array(d['singular_values']);ax.semilogy(range(1,len(sv)+1),sv/sv[0],'-o',ms=3,label=label)
    ax.set(xlabel='Singular index',ylabel='sigma / sigma_max');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('RGB-weighted B2 matrices; shape_only; 420–660nm; 186x186 area detector\nDiagnostic only — no 25-band NNLS or spectral prior',fontsize=10)
    fig.text(.5,.015,NOTICE,ha='center',fontsize=7);fig.tight_layout(rect=(0,.07,1,.9))
    fig.savefig(out/'figures/diagnostic_25bands_verified.png',dpi=150);plt.close(fig)
    worst=max((r for r in rows if r['reconstruction']=='M1_nominal'),key=lambda r:float(r['NRMSE']))
    loss=[r['independently_integrated_outside'] for r in outside_results if r['model']==MODELS[2]]
    addendum=['# EXP2交付复核与关键解释','',NOTICE,'',
              f'最终权威结果目录为`{out}`。首次失败及较早离散Gaussian版本的目录均保留，只按本目录解读结论。',
              '原diagnostic_25bands.png来自通用9带模板，副标题含9带/NNLS通用文字；25带确实只有矩阵预诊断，正确专用图为figures/diagnostic_25bands_verified.png。本次未改写原图，避免掩盖绘图模板问题。',
              '补充figures/mismatch_sam_log.png呈现所有五个失配族的SAM曲线；原mismatch_nrmse_log.png主要呈现四类机制，y方向的全部原始指标仍完整保留。',
              f'独立几何未覆盖权重计算outside的最大相对守恒误差={max(r["relative_conservation_error"] for r in outside_results):.6g}；B2 detector子视场损失范围={min(loss):.9g}–{max(loss):.9g}（相对原归一ROI）。这不是原大ROI未收集的全域光损失。',
              f'Q协议（含失配Q40）最大实际SNR误差={qerr:.6g}dB；P三模型同谱/同P_in的期望总电子相对差最大={pdiff:.6g}。',
              f'最坏M1谱例：{worst["perturbation_id"]}、{worst["spectrum"]}、seed={worst["seed"]}，NRMSE={float(worst["NRMSE"]):.6g}。',
              f'Q40下M1/同模型M0误差比的中位数={np.median([float(r["error_ratio"]) for r in ratios]):.6g}，最大={max(float(r["error_ratio"]) for r in ratios):.6g}；倍数依赖极低的M0噪声基准，应与绝对误差一并看。',
              '协议P中B2阵列实际SNR可为负，但谱误差仍可低于秩亏控制：全ROI读噪总范数包含很多与低维编码子空间正交的分量。该结果不意味着低SNR任意场景可恢复，也不意味着真实相机的相关噪声或失配可忽略。',
              'P低预算/高读噪时，B2的最坏谱误差明显增大；throughput-aware会进一步降低有效电子量。9带在理想噪声下有增益，不等于具备硬件认证。25带条件数约1439.91、最大邻列余弦约0.96273，明显比9带病态，仅支持谨慎的后续探索。',
              '结论仍为CONDITIONAL GO：先针对位置/响应标定及物理数值收敛补证据，不自动开启25带恢复、场景重建或新DOE优化。']
    (out/'interpretation_addendum.md').write_text('\n\n'.join(addendum)+'\n',encoding='utf-8')
    qa=dict(status='PASS',core_checks=len(tests),core_failures=sum(not t['passed'] for t in tests),
            full_solves=len(rows),pilot_solves=record['pilot_solves'],input_files=len(hashes),changed_inputs=changed,artifact_hash_failures=bad,
            Q_max_realized_SNR_error_db=qerr,P_max_expected_electron_model_relative_difference=pdiff,
            max_independent_energy_conservation_error=max(r['relative_conservation_error'] for r in outside_results),
            detector_FOV_loss_B2_range=[min(loss),max(loss)],max_KKT_violation=max(float(r['kkt_violation']) for r in rows),
            zero_estimates=sum(r['zero_estimate']=='True' for r in rows),verifier_sha256=digest(Path(__file__)),
            verifier_command=f"{__import__('sys').executable} -B {Path(__file__)} --output {out}")
    with (out/'delivery_qa.json').open('x',encoding='utf-8') as f:json.dump(qa,f,ensure_ascii=False,indent=2)
    with (out/'delivery_manifest.json').open('x',encoding='utf-8') as f:
        json.dump({str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='delivery_manifest.json'},f,ensure_ascii=False,indent=2)
    print(json.dumps(qa,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
