"""EXP2B交付复核：不新增NNLS或RS求积，独立核验方向、指标和统计。"""
import argparse
from common import *


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--a',type=Path,required=True);parser.add_argument('--b',type=Path,required=True)
    args=parser.parse_args();a=args.a.resolve();b=args.b.resolve();verify_exp2()
    for out in [a,b]:
        if (out/'final_qa.json').exists():raise FileExistsError('拒绝覆盖已有交付QA')
        for name,h in read(out/'artifact_manifest.json').items():
            assert sha(out/name)==h,(out,name)
        for name,d in read(out/'input_manifest.json').items():assert sha(ROOT/name)==d['sha256'],name
        for name,d in read(out/'source_manifest.json').items():assert sha(ROOT/name)==d['sha256']==sha(out/d['snapshot']),name
        assert gitstate()['tracked_diff_sha256']==read(out/'run_config.json')['git_before']['tracked_diff_sha256']
    sys.path.insert(0,str(ROOT/'integration/single_spiral_to_hsi/n03_exp2'))
    import forward as exp2f
    import sampling as sampling
    import perturbations as perturb
    cfg=read(a/'run_config.json');pitch=cfg['detector']['pitch_um']
    edges,det_edges,overlap=sampling.centered_grid(512,pitch)
    points=(det_edges[:-1]+det_edges[1:])/2
    delta=np.zeros((9,512,512));delta[:,255:257,255:257]=.25
    directions=[]
    for axis in ['x','y']:
        for signed in [-.005,.005]:
            cube,_,detail=perturb.detector_perturb(delta,np.array(cfg['weights_RGB']),dict(kind='common_shift_'+axis,level=signed),pitch,edges,det_edges)
            center=np.array([(cube[0].sum(axis=0)*points).sum(),(cube[0].sum(axis=1)*points).sum()])
            along=center[0 if axis=='x' else 1];across=center[1 if axis=='x' else 0]
            assert along*signed>0 and abs(across)<1e-12 and abs(cube[0].sum()-1)<1e-12
            directions.append(dict(axis=axis,signed_pixel=signed,detector_centroid_um=center.tolist(),passed=True,
                                   note='只核验正负号/方向；粗像元中心的质心不强制等于真实亚像元位移'))
    rows=csvread(a/'metrics.csv');summary=csvread(a/'tolerance_summary.csv')
    with np.load(a/'spectral_solutions.npz',allow_pickle=False) as z:
        estimate=z['estimate'];truth=z['truth'];indices=z['spectrum_index']
    assert len(rows)==1224 and estimate.shape==(1224,9) and len(set((r['position_id'],r['spectrum'],r['seed']) for r in rows))==1224
    computed=np.linalg.norm(estimate-truth[indices],axis=1)/np.linalg.norm(truth[indices],axis=1)
    recorded=np.array([float(r['NRMSE']) for r in rows]);metricerr=float(np.max(abs(computed-recorded)));assert metricerr<1e-12
    assert sum(r['position_id']=='origin' for r in rows)==72
    staterr=0.
    for record in summary:
        selected=[float(r['NRMSE']) for r in rows if r['position_id']==record['position_id'] and r['protocol']==record['protocol'] and (record['spectrum_kind']=='ALL' or r['kind']==record['spectrum_kind'])]
        assert len(selected)==int(record['n'])
        for key,val in [('mean',np.mean(selected)),('median',np.median(selected)),('p90',np.quantile(selected,.9)),('max',max(selected))]:
            staterr=max(staterr,abs(float(record['NRMSE_'+key])-val))
    assert staterr<1e-12
    shift=read(a/'shift_manifest.json')
    assert all(s['relative_A_change']>1e-12 for s in shift if s['axis']!='origin')
    qa_a=dict(status='PASS',independent_direction_checks=directions,metric_max_abs_error=metricerr,
              independently_recomputed_summary_max_abs_error=staterr,positions=17,solves=1224,origin_cases=72,
              NNLS_extra_calls=0,RS_extra_calls=0,old_files_unchanged=True,verifier_sha256=sha(Path(__file__)))
    write(a/'final_qa.json',qa_a)
    with np.load(b/'raw/RS_q8.npz') as z:i8=z['intensity_raw'].copy()
    with np.load(b/'raw/RS_q16.npz') as z:i16=z['intensity_raw'].copy()
    recalculated=float(np.abs(i8-i16).sum()/i16.sum());assert abs(recalculated-read(b/'qa.json')['new_vector_L1'])<1e-15
    qa_b=dict(status='PASS',screen_status=read(b/'qa.json')['status'],recomputed_vector_L1=recalculated,
              same_8_point_values=True,RS_extra_calls=0,old_files_unchanged=True,verifier_sha256=sha(Path(__file__)))
    write(b/'final_qa.json',qa_b)
    for out in [a,b]:
        target=out/'logs/source_snapshot/verify_delivery.py'
        with target.open('xb') as f:f.write(Path(__file__).read_bytes())
        write(out/'final_source_manifest.json',{str(p.relative_to(ROOT)):dict(sha256=sha(p),snapshot='logs/source_snapshot/'+p.name)
                                              for p in list(CODE.glob('*.py'))+[CODE.parent/'tests/test_n03_exp2b.py']})
    print(json.dumps(dict(A=qa_a,B=qa_b),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
