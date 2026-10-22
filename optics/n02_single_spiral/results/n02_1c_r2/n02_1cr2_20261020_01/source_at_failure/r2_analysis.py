"""P1/P2局部机制归因；不从稀疏点估算整条边界能量。"""
from r2_common import *


def analyze_p1(out,p1):
    plan=p1['plan'];rows=p1['rows'];asm=p1['asm'];convergence=[];comparisons=[];labels=[];pairs=[]
    by={(r['point_id'],int(r['input_q'])):complex(r['U_real'],r['U_imag']) for r in rows}
    for r in plan:
        pid=r['point_id'];available=[q for q in [1,2,4,8] if (pid,q) in by]
        for a,b in [(1,2),(2,4),(4,8)]:
            valid=(pid,a) in by and (pid,b) in by
            if valid:
                ua=by[pid,a];ub=by[pid,b];field=abs(ua-ub)/max(abs(ub),1e-12);intensity=abs(abs(ua)**2-abs(ub)**2)/max(abs(ub)**2,1e-24)
                converged=field<=.01 and intensity<=.02
            else:field=intensity=None;converged=None
            convergence.append(dict(point_id=pid,x_um=r['x_um'],y_um=r['y_um'],group=r['group'],from_q=a,to_q=b,
               relative_complex_field_change=field,relative_intensity_change=intensity,
               absolute_field_change=abs(by[pid,a]-by[pid,b]) if valid else None,
               phase_change_rad=float(np.angle(by[pid,b]*np.conj(by[pid,a]))) if valid else None,
               diagnostic_converged=converged,status='SIMULATED' if valid else 'NOT_SCHEDULED_OR_RESOURCE_LIMIT',
               reason='' if valid else 'q8仅预注册8点，或此前资源跳过；不是全点8x8认证'))
        best=max(available) if available else None
        if best is None:
            labels.append(dict(point_id=pid,label='INCONCLUSIVE',reason='无RS结果'));continue
        u=by[pid,best];quad=next((c for c in convergence if c['point_id']==pid and c['from_q']==4 and c['to_q']==8),None)
        controlled=bool(quad and quad['diagnostic_converged'])
        residuals=[]
        for pad,(vals,meta) in asm.items():
            idx=next(i for i,p in enumerate(plan) if p['point_id']==pid);v=vals[idx]
            residual=abs(v-u);err=residual/max(abs(u),1e-12);residuals.append(err)
            comparisons.append(dict(point_id=pid,x_um=r['x_um'],y_um=r['y_um'],group=r['group'],inside_pad2=r['inside_pad2'],
               comparison_scope='parallel_diagnostic',ASM_padding=pad,ASM_physical_width_um=2048*pad,
               ASM_U_real=float(v.real),ASM_U_imag=float(v.imag),ASM_intensity=float(abs(v)**2),
               reference_scope='physical_reference',RS_best_q=best,RS_U_real=float(u.real),RS_U_imag=float(u.imag),RS_intensity=float(abs(u)**2),
               relative_complex_residual=err,relative_intensity_residual=abs(abs(v)**2-abs(u)**2)/max(abs(u)**2,1e-24),
               phase_residual_rad=float(np.angle(v*np.conj(u))),RS_4to8_converged=controlled,
               quad_error_abs_estimate=quad['absolute_field_change'] if controlled else None,
               artifact_evidence=bool(controlled and err>.05 and residual>5*quad['absolute_field_change']),
               limitation='离散周期ASM和分片常值源RS的输入表示也不同；残差不能单独分解为环绕'))
        related=[c for c in comparisons if c['point_id']==pid]
        physical=controlled and abs(u)>1e-12
        artifact=any(c['artifact_evidence'] for c in related)
        tag='MIXED' if physical and artifact else 'PHYSICAL_TAIL_SUPPORTED' if physical else 'PERIODIC_OR_SAMPLING_ARTIFACT_SUPPORTED' if artifact else 'INCONCLUSIVE'
        labels.append(dict(point_id=pid,x_um=r['x_um'],y_um=r['y_um'],group=r['group'],
            label=tag,RS_best_q=best,RS_4to8_converged=controlled,RS_intensity=float(abs(u)**2),
            reason='仅局部点；没有整条带面积积分及误差界，不据此给G3 PASS'))
    for r in plan:
        other=r['opposite_id']
        if not other or r['point_id']>other:continue
        for q in [1,2,4,8]:
            if (r['point_id'],q) not in by or (other,q) not in by:continue
            ua=by[r['point_id'],q];ub=by[other,q]
            pairs.append(dict(point_id=r['point_id'],opposite_id=other,input_q=q,x_um=r['x_um'],y_um=r['y_um'],
                intensity_a=float(abs(ua)**2),intensity_b=float(abs(ub)**2),relative_intensity_asymmetry=float((abs(ua)**2-abs(ub)**2)/max(abs(ua)**2+abs(ub)**2,1e-24)),
                phase_opposite_difference_rad=float(np.angle(ua*np.conj(ub))),
                reason='实际螺旋瞳孔无中心对称保证；不能把对边强度不等本身判为数值错误'))
    csvwrite(out/'boundary_quadrature_convergence.csv',convergence);csvwrite(out/'boundary_asm_rs_comparison.csv',comparisons)
    csvwrite(out/'boundary_pointwise_classification.csv',labels);csvwrite(out/'boundary_opposite_edge_pairs.csv',pairs)
    q48=[r for r in convergence if r['from_q']==4 and r['relative_complex_field_change'] is not None]
    counts={name:sum(r['label']==name for r in labels) for name in ['PHYSICAL_TAIL_SUPPORTED','PERIODIC_OR_SAMPLING_ARTIFACT_SUPPORTED','MIXED','INCONCLUSIVE']}
    # 即使个别点稳定，未覆盖所有必要点和全条带，整体前向边界仍不认证。
    overall='INCONCLUSIVE' if not q48 or any(not r['diagnostic_converged'] for r in q48) else ('MIXED' if counts['MIXED'] else 'PHYSICAL_TAIL_SUPPORTED')
    result=dict(label=overall,local_label_counts=counts,quadrature_4to8_tested=len(q48),
       quadrature_4to8_converged=sum(bool(r['diagnostic_converged']) for r in q48),
       max_4to8_complex_change=max((r['relative_complex_field_change'] for r in q48),default=None),
       max_4to8_intensity_change=max((r['relative_intensity_change'] for r in q48),default=None),
       full_boundary_fraction_estimated=False,legacy_G3='FAIL',full_domain_certified=False)
    write(out/'P1_mechanism_decision.json',result)
    plot_boundary(out,p1,comparisons)
    return result,convergence,comparisons,labels


def plot_boundary(out,p1,comp):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(17,5),layout='constrained')
    # 仅沿+x法线的点作点位曲线，禁止解释为条带积分。
    for q in [1,2,4,8]:
        rr=sorted([r for r in p1['rows'] if r['input_q']==q and r['y_um']==.5 and r['x_um']>1900],key=lambda r:r['x_um'])
        if rr:axes[0].semilogy([2047.5-r['x_um'] for r in rr],[r['intensity_raw'] for r in rr],'o-',label=f'RS q={q}')
    for pad in p1['asm']:
        rr=sorted([r for r in comp if r['ASM_padding']==pad and r['y_um']==.5 and r['x_um']>1900],key=lambda r:r['x_um'])
        axes[1].semilogy([2047.5-r['x_um'] for r in rr],[r['ASM_intensity'] for r in rr],'o-',label=f'ASM pad{pad}')
        axes[2].plot([2047.5-r['x_um'] for r in rr],[r['relative_complex_residual'] for r in rr],'o-',label=f'ASM pad{pad} vs RS best')
    for ax in axes:ax.set_xlabel('Distance inward from outer pixel center (um)');ax.legend(fontsize=7)
    axes[0].set_ylabel('RS intensity (um^-2 / incident reference)');axes[1].set_ylabel('Periodic ASM intensity (um^-2)');axes[2].set_ylabel('Relative complex residual')
    fig.suptitle('R2 / frozen B2 / 420nm / sparse pointwise evidence only, not edge fraction / r2_analysis.py')
    fig.savefig(out/'figures/420_boundary_profiles.png',dpi=150);plt.close(fig)


def analyze_p2(out,peak,p2):
    if p2['status']!='COMPLETE':return dict(status='NOT_RUN_RESOURCE_LIMIT')
    center=np.array(peak['common_center_um']);radius=peak['disk_radius_um'];points=p2['points'];rows=[];geom=[]
    # 原冻结各自中心/共同中心：完整旧数组精确回读，绝不冒充本轮RS的新结果。
    rows.extend([dict(scope='frozen_original' if d['mode']=='a_frozen_own' else 'parallel_diagnostic',method='legacy_full_ROI',
         input_q=None,**d,ratio_scope='原完整ROI离散峰比，不替换旧值') for d in peak['frozen_definitions']])
    raw,c,rec=loadcase(OLD/'convergence/cases/dx05_546.1nm.npz');aligned=raw.reshape(512,2,512,2).mean(axis=(1,3));coord=np.arange(512)-255.5
    yy,xx=np.meshgrid(coord,coord,indexing='ij');outside=(xx-center[0])**2+(yy-center[1])**2>radius**2
    main=np.unravel_index(aligned.argmax(),aligned.shape);side=np.unravel_index(np.where(outside,aligned,-1).argmax(),aligned.shape)
    rows.append(dict(scope='parallel_diagnostic',method='legacy_dx05_area_aligned_1um',mode='c_legacy_aligned',condition='dx05_to1um',
        main_xy_um=[float(coord[main[1]]),float(coord[main[0]])],side_xy_um=[float(coord[side[1]]),float(coord[side[0]])],
        main_intensity=float(aligned.max()),side_intensity=float(aligned[side]),outside_ratio=float(aligned.max()/aligned[side]),
        ratio_scope='仅旧数据像元面积对齐；旧细高度重新采样与本轮分片常值源不同'))
    outside_points=np.sum((points-center)**2,axis=1)>radius**2
    for i,p in enumerate(points):geom.append(dict(point_id=peak['points'][i]['point_id'],x_um=p[0],y_um=p[1],
        roles=peak['points'][i]['roles'],distance_common_center_um=float(np.linalg.norm(p-center)),
        physical_radius_um=radius,outside_common_disk=bool(outside_points[i])))
    for q,(value,meta) in p2['fields'].items():
        I=abs(value)**2;main=int(I.argmax());side=int(np.where(outside_points,I,-1).argmax())
        rows.append(dict(scope='physical_reference',method='RS_fixed_piecewise_constant_height',mode='b_common_local_candidates',condition='same_frozen_height',input_q=q,
            center_um=center.tolist(),main_xy_um=points[main].tolist(),side_xy_um=points[side].tolist(),
            main_intensity=float(I[main]),side_intensity=float(I[side]),outside_ratio=float(I[main]/I[side]),
            ratio_scope='预注册局部候选集合最大值，不是独立全局outside_main_disk_ratio',incident_quadrature_energy=meta['incident_quadrature_energy']))
    area=p2['area']
    if area:
        p,v,meta=area;cells=np.array(peak['output_area_cells_um']);I=(abs(v)**2).reshape(-1,4);pp=p.reshape(-1,4,2)
        physical_out=np.sum((pp-center)**2,axis=2)>radius**2
        all_mean=I.mean(axis=1);center_out=np.sum((cells-center)**2,axis=1)>radius**2
        for mode in ['c_area_center_mask','c_area_clipped_physical_radius']:
            if mode=='c_area_center_mask':den=np.where(center_out,all_mean,-1);outside_area=center_out.astype(float)
            else:
                count=physical_out.sum(axis=1);den=np.where(count>0,(I*physical_out).sum(axis=1)/np.maximum(count,1),-1)
                outside_area=count/4
            mi=int(all_mean.argmax());si=int(den.argmax())
            rows.append(dict(scope='physical_reference',method='RS_source_q4_detector_area2',mode=mode,condition='same_frozen_height',input_q=4,
                main_xy_um=cells[mi].tolist(),side_xy_um=cells[si].tolist(),main_intensity=float(all_mean[mi]),side_intensity=float(den[si]),
                outside_ratio=float(all_mean[mi]/den[si]),side_outside_area_um2=float(outside_area[si]),
                ratio_scope='仅预注册1um候选像元；输出2x2中点面积近似未做输出求积收敛，不是全局门禁'))
        csvwrite(out/'peak_detector_area_cells.csv',[dict(x_um=p[0],y_um=p[1],mean_intensity=all_mean[i],outside_subpixel_fraction=float(physical_out[i].mean())) for i,p in enumerate(cells)])
    convergence=[]
    for a,b in [(1,2),(2,4)]:
        u=p2['fields'][a][0];v=p2['fields'][b][0]
        for i,p in enumerate(points):convergence.append(dict(point_id=peak['points'][i]['point_id'],from_q=a,to_q=b,
            relative_field_change=float(abs(u[i]-v[i])/max(abs(v[i]),1e-12)),relative_intensity_change=float(abs(abs(u[i])**2-abs(v[i])**2)/max(abs(v[i])**2,1e-24))))
    csvwrite(out/'peak_mask_sensitivity_rs.csv',rows);csvwrite(out/'peak_candidate_geometry.csv',geom);csvwrite(out/'peak_quadrature_convergence.csv',convergence)
    rsrows=[r for r in rows if r['method']=='RS_fixed_piecewise_constant_height']
    difference=abs(rsrows[-1]['outside_ratio']-rsrows[0]['outside_ratio'])
    result=dict(status='COMPLETED_LOCAL_DIAGNOSTIC',RS_q1_q4_local_candidate_ratio_difference=difference,
        output_area_done=area is not None,full_ROI_RS_certified=False,source_q8_done=False,old_G3='FAIL')
    write(out/'P2_mechanism_decision.json',result);plot_peak(out,rows,geom)
    return result


def plot_peak(out,rows,geom):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(15,6),layout='constrained')
    label=[];ratios=[]
    for r in rows:
        label.append(f"{r.get('condition','')} / {r['mode']} / q={r.get('input_q')}");ratios.append(r['outside_ratio'])
    axes[0].barh(np.arange(len(rows)),ratios);axes[0].set_yticks(np.arange(len(rows)),label,fontsize=6);axes[0].set_xlabel('Intensity ratio (definitions differ; no gate replacement)')
    for r in geom:axes[1].scatter(r['x_um'],r['y_um'],color='red' if r['outside_common_disk'] else 'blue');axes[1].annotate(r['point_id'],(r['x_um'],r['y_um']),fontsize=7)
    axes[1].set(xlabel='x (um)',ylabel='y (um)',title='Pre-registered candidate locations / common disk membership');axes[1].axis('equal')
    fig.suptitle('R2 / 546.1nm / frozen originals vs parallel diagnostics vs local physical reference / r2_analysis.py')
    fig.savefig(out/'figures/546_peak_mask_comparison.png',dpi=150);plt.close(fig)
