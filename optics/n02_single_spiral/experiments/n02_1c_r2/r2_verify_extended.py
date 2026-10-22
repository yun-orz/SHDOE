"""独立补充复核P2、对边、点分类，并用CPU全源单点RS交叉检验GPU。"""
import sys
sys.dont_write_bytecode=True
import argparse
from r2_common import *


def verify(out):
    boundary=read(out/'boundary_sample_plan.json')['points'];fields={};asm={}
    for path in (out/'raw').glob('P1_RS_q*.npz'):
        with np.load(path) as z:
            meta=json.loads(z['meta_json'].item());q=meta['input_subdivision']
            for pid,u in zip(z['point_id'],z['field_without_global_piston']):fields[str(pid),q]=u
    for pad in [2,4]:
        with np.load(out/f'raw/P1_ASM_pad{pad}_selected.npz') as z:asm[pad]={str(pid):u for pid,u in zip(z['point_id'],z['field_without_global_piston'])}
    count=0
    for row in csvread(out/'boundary_asm_rs_comparison.csv'):
        pid=row['point_id'];q=int(row['RS_best_q']);pad=int(row['ASM_padding']);u=fields[pid,q];v=asm[pad][pid]
        e=abs(v-u)/max(abs(u),1e-12);assert abs(e-float(row['relative_complex_residual']))<1e-12;count+=1
    pairs=csvread(out/'boundary_opposite_edge_pairs.csv')
    for row in pairs:
        a=fields[row['point_id'],int(row['input_q'])];b=fields[row['opposite_id'],int(row['input_q'])]
        e=(abs(a)**2-abs(b)**2)/max(abs(a)**2+abs(b)**2,1e-24)
        assert abs(e-float(row['relative_intensity_asymmetry']))<1e-12
    plan=read(out/'peak_sample_plan.json');points=np.array([[r['x_um'],r['y_um']] for r in plan['points']]);center=np.array(plan['common_center_um']);R=plan['disk_radius_um']
    rr=csvread(out/'peak_mask_sensitivity_rs.csv');checked=0
    for row in rr:
        if row['method']=='RS_fixed_piecewise_constant_height':
            q=int(row['input_q'])
            with np.load(out/f'raw/P2_RS_q{q}.npz') as z:I=abs(z['field_without_global_piston'])**2
            good=np.linalg.norm(points-center,axis=1)>R
            ratio=float(I.max()/I[good].max());assert abs(ratio-float(row['outside_ratio']))<1e-12;checked+=1
    with np.load(out/'raw/P2_RS_q4_output_area2.npz') as z:
        I=abs(z['field_without_global_piston'].reshape(-1,4))**2;xy=z['points_um'].reshape(-1,4,2);cells=z['output_cell_centers_um']
    physical=np.linalg.norm(xy-center,axis=2)>R;means=I.mean(axis=1)
    outside=np.linalg.norm(cells-center,axis=1)>R
    ratios=dict(c_area_center_mask=float(means.max()/means[outside].max()),
        c_area_clipped_physical_radius=float(means.max()/max(np.mean(v[m]) for v,m in zip(I,physical) if m.any())))
    for row in rr:
        if row['mode'] in ratios:assert abs(ratios[row['mode']]-float(row['outside_ratio']))<1e-12;checked+=1
    # 一个真实边界点、全原入瞳、4x4求积的独立NumPy路径，不调用GPU主求解器。
    cfg,h,mask,src=source_pixels();chosen=next(r for r in boundary if r['x_um']==2047.5 and r['y_um']==.5)
    offsets=(np.arange(4)+.5)/4-.5;oy,ox=np.meshgrid(offsets,offsets,indexing='ij');value=0j
    w=.42;k=2*np.pi/w;s=180000.;z=22495.;dn=1.5292+.008/w**2-1
    start=time.perf_counter()
    for first in range(0,len(src['x']),4096):
        x=src['x'][first:first+4096,None]+ox.ravel()[None,:];y=src['y'][first:first+4096,None]+oy.ravel()[None,:]
        height=src['height'][first:first+4096,None];rin=np.sqrt(s*s+x*x+y*y)
        source=src['K']*s/rin*np.exp(1j*k*((x*x+y*y)/(rin+s)+dn*height))
        d2=(x-2047.5)**2+(y-.5)**2;dist=np.sqrt(z*z+d2)
        kernel=z/(1j*w)*np.exp(1j*k*d2/(dist+z))/dist**2*(1+1j/(k*dist))
        value+=np.sum(source*kernel)/16
    ref=fields[chosen['point_id'],4];absolute=float(abs(value-ref));relative=absolute/max(abs(ref),1e-12)
    assert absolute<1e-12 and relative<1e-7
    return dict(status='PASS',P1_ASM_RS_rows_recomputed=count,opposite_pairs_recomputed=len(pairs),P2_physical_ratio_rows_recomputed=checked,
        CPU_full_pupil_spot_point_id=chosen['point_id'],CPU_RS_q=4,CPU_GPU_absolute_field_difference=absolute,
        CPU_GPU_relative_field_difference=relative,CPU_spot_seconds=time.perf_counter()-start,
        source_height_sha256=sha(OLD/'B2/height_um.npy'),no_new_wavelength_or_sample_point=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args();out=ROOT/'results/n02_1c_r2'/args.run_id
    result=verify(out);write(out/'verification_extended.json',result)
    write(out/'verification_extended_manifest.json',dict(base_manifest_sha256=sha(out/'manifest.json'),
       verification_sha256=sha(out/'verification_extended.json'),verification_source_sha256=sha(__file__),
       source_path=str(Path(__file__).relative_to(ROOT)),scope='补充独立只读重算，旧主归档不覆盖'))
    print(json.dumps(result,ensure_ascii=False,indent=2))
