"""先P1后P2；所有求积场值保存，失败/跳过不抹除。"""
from r2_common import *
from r2_solver import rs,periodic_points
import traceback


def complex_rows(fields,points,w,meta):
    return [dict(point_id=r['point_id'],x_um=r['x_um'],y_um=r['y_um'],wavelength_nm=w,input_q=meta['input_subdivision'],
       U_real=float(u.real),U_imag=float(u.imag),intensity_raw=float(abs(u)**2),incident_quadrature_energy=meta['incident_quadrature_energy'],
       seconds_for_level=meta['seconds'],method='physical_reference_RS_piecewise_constant_height',
       status='SIMULATED',reason='全局exp(ikz)已在全部模型共同移除；不作ROI重归一') for r,u in zip(points,fields)]


def source_field(src,cfg,w):
    wl=w/1000.;s=cfg['object_mm']*1000;k=2*np.pi/wl;dn=1.5292+.008/wl**2-cfg['n_env']
    x=src['x'];y=src['y'];r2=x*x+y*y;dist=np.sqrt(s*s+r2)
    v=src['K']*s/dist*np.exp(1j*k*(r2/(dist+s)+dn*src['height']))
    u=np.zeros((2048,2048),complex);u[(y+1023.5).astype(int),(x+1023.5).astype(int)]=v
    return u


def run_p1(out,cfg,src,resource,plan):
    started=time.perf_counter();points=np.array([[r['x_um'],r['y_um']] for r in plan]);fields={};rows=[];calls=[];asm={};skips=[]
    if not resource['RS_allowed']:
        write(out/'P1_execution_status.json',dict(status='NOT_RUN_RESOURCE_LIMIT',reason='RAM低于512MiB分块安全下限'))
        return dict(fields=fields,rows=rows,asm=asm,plan=plan,seconds=0.,status='NOT_RUN_RESOURCE_LIMIT')
    for q in [1,2,4]:
        event(out,event='RS_P1_START',q=q,points=len(plan),height_file_sha256=sha(OLD/'B2/height_um.npy'),resource=memory())
        try:
            value,meta=rs(src,points,420,cfg,q,resource['RS_device'])
        except torch.OutOfMemoryError:
            skips.append(dict(q=q,status='NOT_RUN_RESOURCE_LIMIT',reason=traceback.format_exc()));break
        fields[q]=(points.copy(),value,meta);calls.append(meta)
        npz(out/f'raw/P1_RS_q{q}.npz',points_um=points,point_id=np.asarray([r['point_id'] for r in plan]),
            field_without_global_piston=value,intensity_raw=abs(value)**2,meta_json=json.dumps(clean(meta),ensure_ascii=False))
        rows.extend(complex_rows(value,plan,420,meta));event(out,event='RS_P1_COMPLETE',q=q,**meta)
        print(f'P1 420nm RS {q}x{q} {len(plan)}点 {meta["seconds"]:.2f}s 入瞳面积功率={meta["incident_quadrature_energy"]:.12f}',flush=True)
    subset=[i for i,r in enumerate(plan) if r['q8_preregistered']]
    q1time=calls[0]['seconds'] if calls else None
    predicted=q1time*64*len(subset)/len(plan) if q1time else None
    if 4 in fields and predicted is not None and time.perf_counter()-started+predicted<300:
        q=8;pp=points[subset];subplan=[plan[i] for i in subset]
        value,meta=rs(src,pp,420,cfg,q,resource['RS_device']);fields[q]=(pp,value,meta);calls.append(meta)
        npz(out/'raw/P1_RS_q8.npz',points_um=pp,point_id=np.asarray([r['point_id'] for r in subplan]),
            field_without_global_piston=value,intensity_raw=abs(value)**2,meta_json=json.dumps(clean(meta),ensure_ascii=False))
        rows.extend(complex_rows(value,subplan,420,meta));event(out,event='RS_P1_COMPLETE',q=8,**meta)
        print(f'P1 420nm RS 8x8 预注册{subset.__len__()}点 {meta["seconds"]:.2f}s',flush=True)
    else:skips.append(dict(q=8,status='NOT_RUN_RESOURCE_LIMIT',reason='固定可选8点的预测时间超过P1预算或4x4未完成',predicted_seconds=predicted))
    # 同一1um中点离散输入的周期ASM，仅求计划坐标。无pad5/pad8、无全域输出。
    u=source_field(src,cfg,420)
    for rplan in resource['selected_point_ASM']:
        pad=rplan['pad']
        if not rplan['allowed']:
            skips.append(dict(padding=pad,status='NOT_RUN_RESOURCE_LIMIT',reason='选点ASM频谱GPU/主机预算不允许'));continue
        try:
            event(out,event='SELECTED_ASM_START',padding=pad,points=len(plan),resource=memory())
            value,meta=periodic_points(u,points,420,cfg,pad)
            # 回读ROI内控制点验证与原完整FFT传播相同的强度，不将边界值从ROI捏造出来。
            refpath=OLD/'B2/cases/420nm.npz' if pad==2 else OLD/'convergence/cases/pad4_420nm.npz'
            raw,c,ref=loadcase(refpath);errs=[]
            for (x,y),v in zip(points,value):
                if abs(x)<256 and abs(y)<256:
                    ii=int(round(y+255.5));jj=int(round(x+255.5));errs.append(abs(abs(v)**2-raw[ii,jj]))
            error=max(errs);assert error<1e-10,f'选点ASM与冻结ROI不一致：{error}'
            meta['frozen_roi_control_max_intensity_error']=error
            meta['frozen_total_energy_difference']=meta['finite_periodic_energy']-ref['raw_energy']
            asm[pad]=(value,meta)
            npz(out/f'raw/P1_ASM_pad{pad}_selected.npz',points_um=points,point_id=np.asarray([r['point_id'] for r in plan]),
                field_without_global_piston=value,intensity_raw=abs(value)**2,meta_json=json.dumps(clean(meta),ensure_ascii=False))
            event(out,event='SELECTED_ASM_COMPLETE',**meta)
            print(f'P1 ASM pad{pad} 选点 {meta["seconds"]:.2f}s 原ROI控制误差={error:.3g}',flush=True)
        except torch.OutOfMemoryError:
            skips.append(dict(padding=pad,status='NOT_RUN_RESOURCE_LIMIT',reason=traceback.format_exc()));torch.cuda.empty_cache()
    csvwrite(out/'boundary_pointwise_rs.csv',rows)
    write(out/'P1_execution_status.json',dict(status='COMPLETED_LOCAL_DIAGNOSTIC' if all(q in fields for q in [1,2,4]) else 'PARTIAL_RESOURCE_LIMIT',
          RS_q_done=sorted(fields),ASM_pads_done=sorted(asm),optional_q8_preselected_points=len(subset),skips=skips,
          seconds=time.perf_counter()-started,source_height_sha256=sha(OLD/'B2/height_um.npy')))
    return dict(fields=fields,rows=rows,asm=asm,plan=plan,seconds=time.perf_counter()-started,status='COMPLETE' if 4 in fields else 'PARTIAL_RESOURCE_LIMIT')


def run_p2(out,cfg,src,resource,peak,p1):
    if p1['status']!='COMPLETE' or p1['seconds']>=300 or not resource['RS_allowed']:
        write(out/'P2_execution_status.json',dict(status='NOT_RUN_RESOURCE_LIMIT',reason='P1未完成或耗尽300秒优先预算；不自动补跑'))
        textfile(out/'N02_peak_ratio_mechanism.md','# P2\n\nNOT_RUN_RESOURCE_LIMIT。P1优先预算未满足，不以省略P1换取P2。固定计划已保留peak_sample_plan.json，下一轮独立排期。\n')
        csvwrite(out/'peak_mask_sensitivity_rs.csv',[dict(status='NOT_RUN_RESOURCE_LIMIT',reason='P1优先预算')])
        return dict(status='NOT_RUN_RESOURCE_LIMIT',fields={})
    start=time.perf_counter();points=np.array([[r['x_um'],r['y_um']] for r in peak['points']]);fields={};rows=[]
    for q in [1,2,4]:
        value,meta=rs(src,points,546.1,cfg,q,resource['RS_device']);fields[q]=(value,meta)
        npz(out/f'raw/P2_RS_q{q}.npz',points_um=points,point_id=np.asarray([r['point_id'] for r in peak['points']]),
            field_without_global_piston=value,intensity_raw=abs(value)**2,meta_json=json.dumps(clean(meta),ensure_ascii=False))
        rows.extend(complex_rows(value,peak['points'],546.1,meta));event(out,event='RS_P2_COMPLETE',q=q,**meta)
        print(f'P2 546.1nm RS {q}x{q} {len(points)}候选点 {meta["seconds"]:.2f}s',flush=True)
    csvwrite(out/'peak_candidates_rs.csv',rows)
    cells=np.array(peak['output_area_cells_um']);off=np.array([[-.25,-.25],[-.25,.25],[.25,-.25],[.25,.25]])
    expanded=(cells[:,None,:]+off[None,:,:]).reshape(-1,2)
    predicted=fields[1][1]['seconds']*16*len(expanded)/len(points)
    area=None
    if time.perf_counter()-start+predicted<180:
        value,meta=rs(src,expanded,546.1,cfg,4,resource['RS_device']);area=(expanded,value,meta)
        npz(out/'raw/P2_RS_q4_output_area2.npz',points_um=expanded,output_cell_centers_um=cells,field_without_global_piston=value,
            intensity_raw=abs(value)**2,meta_json=json.dumps(clean(meta),ensure_ascii=False))
        event(out,event='RS_P2_DETECTOR_AREA_COMPLETE',**meta)
    write(out/'P2_execution_status.json',dict(status='COMPLETED_LOCAL_DIAGNOSTIC',RS_q_done=sorted(fields),
         output_area2_status='SIMULATED' if area else 'NOT_RUN_RESOURCE_LIMIT',seconds=time.perf_counter()-start,
         source_height_sha256=sha(OLD/'B2/height_um.npy'),limitation='仅固定少量候选点/像元，不是完整ROI独立场'))
    return dict(status='COMPLETE',fields=fields,points=points,area=area)


def check_p3(out):
    loc=module('r2_old_locators',ROOT/'experiments/n02_1c_r/p0b_locators.py')
    a,c,r=loadcase(OLD/'B2/cases/425nm.npz');q=loc.quadratic(a,c)
    old=csvread(UP/'diagnostics/425_fit_audit.csv')[0]
    assert np.allclose(q['unconstrained_offset_pixels'],json.loads(old['unconstrained_offset_pixels']),atol=1e-12,rtol=0)
    assert np.allclose(q['hessian_eigenvalues'],json.loads(old['hessian_eigenvalues']),atol=1e-12,rtol=0)
    z=np.load(UP/'propagation/RS_points_425nm.npz');pick=z['point_kind']=='core_native_grid';p=z['points_um'][pick];truth=z['intensity_raw'][pick]
    assert len(truth)==49;stats=[]
    for tag,path in [('pad2',OLD/'B2/cases/425nm.npz'),('pad4',OLD/'convergence/cases/pad4_425nm.npz')]:
        raw,c,r=loadcase(path);vals=np.array([raw[int(round(y+255.5)),int(round(x+255.5))] for x,y in p])
        err=float(abs(vals-truth).sum()/truth.sum())
        reference=next(row for row in csvread(UP/'diagnostics/RS_core_error_summary.csv') if float(row['wavelength_nm'])==425 and row['method']==tag)
        assert abs(err-float(reference['core49_relative_L1']))<1e-12
        stats.append(dict(method=tag,RS49_relative_L1=err))
    intervals=csvread(UP/'diagnostics/blue_domains_trajectory_v2.csv');checked=0
    for row in intervals:
        if row['condition']=='pad4' and row['actual_delta_wavelength_nm']:
            dw=float(row['actual_delta_wavelength_nm']);assert dw==5
            delta=float(row['delta_angle_deg']);gate=.4*dw<=delta<=1.8*dw
            assert gate==(row['actual_spacing_scaled_gate']=='True');checked+=1
    write(out/'425_evaluator_evidence_check.json',dict(status='PASS',offset=q['unconstrained_offset_pixels'],hessian_eigenvalues=q['hessian_eigenvalues'],
           RS49=stats,pad4_five_nm_intervals_checked=checked,old_G2='FAIL',new_425_propagations=0))
    textfile(out/'425_evaluator_evidence_check.md',f'''# 425nm保留任务

最终标记：**评价器不稳定有证据，单圈物理模态尚未完全认证**。
独立从原NPZ复现驻点偏移{q['unconstrained_offset_pixels']}pixel，负定Hessian{q['hessian_eigenvalues']}，不是双峰失效证据。
RS仍为上轮1um中点源求积；同一49坐标重新计算pad2/pad4相对强度L1：{stats}，与源CSV相符。
v2的pad4实际5nm间隔共核对{checked}个（含两种定位器），门按0.4*5至1.8*5度；完整pad2/开放Fresnel 1nm轨迹独立保留。
本轮425nm新传播0次；没有新全带证据，旧G2仍FAIL。
''')
