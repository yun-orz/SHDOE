"""结果完成后的独立几何与统计审计，不更改既有实验产物。"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from forward_adapter import ForwardAdapter, f, perturbations, noise
from position_solver import joint_solve
from run_exp3 import read, write, text, sha, NOTICE
from verify_exp3 import verify


def main(out):
    verification=verify(out);assert verification['passed'],verification
    model=ForwardAdapter();config=read(out/'run_config.json');checks=[]
    def check(name,error,tolerance):
        checks.append(dict(name=name,error=float(error),tolerance=tolerance,passed=bool(error<=tolerance)))
    # 独立密集重叠算式，不调用原sampling.rebin或overlap_matrix。
    p=np.array([.23,-.17]);edges=model.edges;det=model.det_edges
    def dense(delta):
        return np.maximum(0,np.minimum(det[1:,None],edges[None,1:]+delta)-np.maximum(det[:-1,None],edges[None,:-1]+delta))
    wx=dense(p[0]*model.pitch);wy=dense(p[1]*model.pitch)
    independent=np.stack([wy@h@wx.T for h in model.fine]);capture=independent.sum(axis=(1,2));independent/=capture[:,None,None]
    cube,captured=model.cube(p)
    check('独立密集几何积分与半像元边界',np.linalg.norm(cube-independent)/np.linalg.norm(cube),1e-13)
    check('逐带原始capture一致',np.max(abs(capture-captured)),1e-13)
    expected,_,detail=perturbations.detector_perturb(model.fine,model.weights,dict(kind='gaussian_blur',level=.1),model.pitch,model.edges,model.det_edges)
    expected/=expected.sum(axis=(1,2))[:,None,None]
    blurred,_=model.cube([0,0],.1)
    check('高斯展宽与EXP2已验收API一致',np.linalg.norm(expected-blurred)/np.linalg.norm(expected),1e-13)
    with (out/'metrics.csv').open(encoding='utf-8-sig',newline='') as h:rows=list(csv.DictReader(h))
    stage='full' if any(r['stage']=='full' for r in rows) else 'pilot'
    mainrows=[r for r in rows if r['stage']==stage];js=[r for r in mainrows if r['method']=='J']
    traces=read(out/'optimization_traces.json');endings=[e for obs,t in traces.items() if obs.startswith(stage+'_') for e in t['terminations']]
    # 按已固定数据定义复现观测，复跑两个案例及直接目标；不用于重新选算法。
    for protocol in ['noiseless','Q40']:
        r=next(r for r in js if r['protocol']==protocol and r['position_id']=='0')
        truth=np.array(json.loads(r['truth']));position=[float(r['dx_true']),float(r['dy_true'])];a,_=model.matrix(position);clean=a@truth
        y=clean if protocol=='noiseless' else noise.protocol_q(clean,noise.gaussian_direction(int(r['seed']),int(r['spectrum_index']),len(clean)),40)[0]
        repeated=joint_solve(y,model)
        check('重复运行位置/'+protocol,np.linalg.norm(np.array(repeated['position'])-[float(r['dx_hat']),float(r['dy_hat'])]),1e-14)
        check('重复运行光谱/'+protocol,np.linalg.norm(repeated['estimate']-json.loads(r['estimate'])),1e-14)
        ah,_=model.matrix(repeated['position']);direct=float(np.linalg.norm(ah@repeated['estimate']-y)**2/np.linalg.norm(y)**2)
        check('搜索目标与直接残差/'+protocol,abs(direct-repeated['loss']),1e-18)
        if protocol=='noiseless':
            fixed=next(t for t in mainrows if t['observation']==r['observation'] and t['method']=='F')
            check('原点J退化为F光谱',np.linalg.norm(repeated['estimate']-json.loads(fixed['estimate'])),1e-10)
    pairs=[]
    for protocol in ['noiseless','Q40']:
        rr=[r for r in js if r['protocol']==protocol];deltas=[];gaps=[];ratio=[]
        for r in rr:
            group=[t for t in mainrows if t['observation']==r['observation']]
            fixed=next(t for t in group if t['method']=='F');oracle=next(t for t in group if t['method']=='O')
            deltas.append(float(fixed['NRMSE'])-float(r['NRMSE']));gaps.append(float(r['NRMSE'])-float(oracle['NRMSE']))
            if float(fixed['NRMSE'])>1e-12:ratio.append(float(r['NRMSE'])/float(fixed['NRMSE']))
        pairs.append(dict(protocol=protocol,n=len(rr),J_less_NRMSE_than_F_fraction=float(np.mean(np.array(deltas)>1e-12)),F_minus_J_NRMSE_mean=float(np.mean(deltas)),F_minus_J_NRMSE_median=float(np.median(deltas)),J_minus_O_NRMSE_mean=float(np.mean(gaps)),J_minus_O_NRMSE_median=float(np.median(gaps)),J_over_F_NRMSE_median_excluding_numerical_zero_F=float(np.median(ratio))))
    maps=[]
    for item in read(out/'objective_maps.json'):
        z=np.array(item['relative_squared_residual']);iy,ix=np.unravel_index(np.argmin(z),z.shape)
        maps.append(dict(observation=item['observation'],sampled_min=float(z.min()),sampled_max=float(z.max()),argmin_grid=[item['x'][ix],item['y'][iy]],grid_dynamic_range=float(z.max()-z.min()),scope='局部有限网格；不认证全域唯一性'))
    worst=sorted(js,key=lambda r:float(r['position_error_pixel']),reverse=True)[:10]
    report=dict(base_verification=verification,checks=checks,all_pass=all(c['passed'] for c in checks),paired_comparisons=pairs,
                local_terminations=dict(total=len(endings),converged=sum(e['success'] for e in endings),budget_terminated=sum(not e['success'] for e in endings)),
                solution_boundary_fraction=float(np.mean([r['boundary']=='True' for r in js])),
                signal_norm_range=[min(float(r['y_norm']) for r in js),max(float(r['y_norm']) for r in js)],
                worst_position_cases=[{k:r[k] for k in ['spectrum','kind','position_id','seed','position_error_pixel','NRMSE','dx_hat','dy_hat']} for r in worst],objective_map_diagnostics=maps,
                normalization_note=config['normalization'],blur_API=detail)
    write(out/'independent_audit.json',report)
    text(out/'independent_audit.md','# EXP3独立复核\n\n'+NOTICE+'\n\n独立密集几何积分、半像元边界、EXP2连续高斯API、两例复跑与原点退化检查：'+('PASS' if report['all_pass'] else 'FAIL')+'。统计逐行回算、输入/源码/原始产物哈希、O/F/J同噪声与样本完整性核验通过。\n\n'+json.dumps(report['paired_comparisons'],ensure_ascii=False,indent=2)+'\n\n局部优化终止统计：'+json.dumps(report['local_terminations'],ensure_ascii=False)+'。预算终止保留其最好候选；不属于内层NNLS失败，也不证明达到连续极小值。所有例子均遵守119候选预算，未追加优化轮次。最坏定位案例与局部目标动态图幅见independent_audit.json；有限采样不认证全域唯一性。\n')
    write(out/'final_delivery_manifest.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
    print(json.dumps(report,ensure_ascii=False,indent=2));assert report['all_pass']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);main(parser.parse_args().output)
