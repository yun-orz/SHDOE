"""只读独立数值/哈希复核，不写回历史文件。"""
from r2_common import *
import argparse


def numerical_verify(out):
    fields={};checked=0;maxerr=0.
    for p in (out/'raw').glob('P1_RS_q*.npz'):
        with np.load(p,allow_pickle=False) as z:
            q=json.loads(z['meta_json'].item())['input_subdivision'];u=z['field_without_global_piston'];I=z['intensity_raw']
            err=float(abs(I-abs(u)**2).max());assert err<1e-20;maxerr=max(maxerr,err)
            for pid,v in zip(z['point_id'],u):fields[str(pid),q]=v
            checked+=len(u)
    for row in csvread(out/'boundary_quadrature_convergence.csv'):
        pid=row['point_id'];a=int(row['from_q']);b=int(row['to_q'])
        if row['relative_complex_field_change']:
            u=fields[pid,a];v=fields[pid,b]
            err=abs(u-v)/max(abs(v),1e-12)
            assert abs(err-float(row['relative_complex_field_change']))<1e-12
            val=abs(abs(u)**2-abs(v)**2)/max(abs(v)**2,1e-24)
            assert abs(val-float(row['relative_intensity_change']))<1e-12
    for row in csvread(out/'boundary_pointwise_rs.csv'):
        u=fields[row['point_id'],int(row['input_q'])];assert abs(u-complex(float(row['U_real']),float(row['U_imag'])))<1e-15
    for pad in [2,4]:
        p=out/f'raw/P1_ASM_pad{pad}_selected.npz'
        if p.exists():
            with np.load(p) as z:
                meta=json.loads(z['meta_json'].item());assert meta['frozen_roi_control_max_intensity_error']<1e-10
    # 输入求积的所有q沿用同一K，不允许逐级强制归一。
    Ks=[]
    for p in (out/'raw').glob('P*_RS_*.npz'):
        with np.load(p) as z:
            meta=json.loads(z['meta_json'].item());Ks.append(meta['fixed_K'])
            assert np.isfinite(z['intensity_raw']).all() and np.all(z['intensity_raw']>=0)
    assert len(set(Ks))<=1
    return dict(P1_raw_fields_checked=checked,max_intensity_recalculation_error=maxerr,fixed_K_same_all_levels=True,
       partial_outputs_respected=True,no_full_edge_integration=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    out=ROOT/'results/n02_1c_r2'/args.run_id;m=read(out/'manifest.json');files=read(out/'artifact_manifest.json')
    assert sha(out/'artifact_manifest.json')==m['artifact_manifest_sha256']
    for p,h in files.items():assert sha(out/p)==h,f'输出SHA失败：{p}'
    for p,h in m['source_hashes'].items():assert sha(ROOT/p)==h,f'源码SHA失败：{p}'
    for p,h in read(out/'input_hashes.json').items():assert sha(p)==h,f'输入SHA失败：{p}'
    result=numerical_verify(out)
    assert read(OLD/'gates.json')['G2']['status']==read(OLD/'gates.json')['G3_Numerics']['status']=='FAIL'
    assert read(UP/'P0B_gate_decision_v2.json')['status']=='INCONCLUSIVE'
    print(json.dumps(dict(status='PASS',input_hashes=len(read(out/'input_hashes.json')),output_hashes=len(files),numerical=result,
       scientific_status=m['scientific_status'],old_G2_G3='FAIL_UNCHANGED'),ensure_ascii=False,indent=2))
