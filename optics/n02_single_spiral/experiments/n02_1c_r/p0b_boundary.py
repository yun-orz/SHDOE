"""工作包B：域尺寸矩阵、旧失败分解与开放边界独立参照。"""
from p0b_common import *
from p0b_locators import quadratic,interpolate
from p0b_propagation import acquire_asm,acquire_fresnel,rs_points
from scipy.ndimage import map_coordinates,label


def run_b(out,cfg,h,d,plan):
    waves=list(range(420,431))+[546.1,660];sources={};domain=[];references={};comparisons=[];ratios=[];rsrows=[]
    def add(w,tag,item,new=False):
        raw,c,r=item;sources[w,tag]=item
        baseline=loadcase(OLD/'B2/cases'/f'{w:g}nm.npz')[2]
        if tag in ['pad2','pad4','pad5','dx05']:
            total=r['raw_energy'];edge=r['edge_fraction'];pitch=r['pitch_um'];n=r['size']*r['padding']
            domain.append(dict(wavelength_nm=w,condition=tag,source='NEW_FIXED_HEIGHT' if new else 'READ_ONLY_LEGACY',
                physical_width_um=n*pitch,N_output=n,dx_um=pitch,boundary_strip_width_um=16.,strip_pixels=int(round(16/pitch)),
                candidate_edge=edge,frozen_baseline_edge=baseline['edge_fraction'],candidate_edge_gate=edge<.001,
                combined_gate=max(edge,baseline['edge_fraction'])<.001,finite_domain_energy=total,roi_energy_incident=r['crop_energy'],
                ROI_fraction_finite_domain=r['crop_energy']/total,global_parseval_error=r['spectral_energy_accounting_error'],
                outside_ratio=r['outside_main_disk_ratio'],frozen_fit_status=r['n01_status'],
                height_array_sha256=r['height_array_sha256'],same_sampled_height=(r['height_array_sha256']==arrsha(h)),
                note='dx05是旧连续设计重采样再量化，不与原高度数组等同' if tag=='dx05' else '同一固定1um物理高度数组'))
    for w in waves:
        add(w,'pad2',loadcase(OLD/'B2/cases'/f'{w:g}nm.npz'))
        p=OLD/'convergence/cases'/f'pad4_{w:g}nm.npz'
        if p.exists():add(w,'pad4',loadcase(p))
        elif plan[4]['allowed']:add(w,'pad4',acquire_asm(out,w,4,cfg,h,d,plan),True)
        if w in [420,425,430,546.1,660]:add(w,'dx05',loadcase(OLD/'convergence/cases'/f'dx05_{w:g}nm.npz'))
    for w in [420,425,546.1,660]:
        if plan[5]['allowed']:add(w,'pad5',acquire_asm(out,w,5,cfg,h,d,plan),True)
    # 输出同一512um物理ROI，不因更大域改变观察窗口。
    for w in waves:
        ref,c,meta=acquire_fresnel(out,w,cfg,h,d);references[w]=(ref,c,meta)
        ref_loc=interpolate(ref,c,3,starts=4);ref_center=(ref_loc['x_um'],ref_loc['y_um'])
        ref_m=independent_metrics(ref,c,w,cfg,ref_center)
        for (wave,tag),(raw,coords,r) in sources.items():
            if wave!=w:continue
            aligned=raw
            if raw.shape[0]==1024:aligned=raw.reshape(512,2,512,2).mean(axis=(1,3))
            p=aligned/aligned.sum();q=ref/ref.sum();loc=interpolate(raw,coords,3,starts=4)
            frozen=quadratic(raw,coords);m=independent_metrics(raw,coords,w,cfg,ref_center)
            common_base=independent_metrics(sources[w,'pad2'][0],sources[w,'pad2'][1],w,cfg,ref_center)
            common_grid=independent_metrics(aligned,c,w,cfg,ref_center)
            ratios.append(dict(wavelength_nm=w,condition=tag,frozen_center_x_um=frozen['x_um'],frozen_center_y_um=frozen['y_um'],
                common_center_x_um=ref_center[0],common_center_y_um=ref_center[1],native_frozen_outside_ratio=r['outside_main_disk_ratio'],
                native_common_center_outside_ratio=m['outside_ratio'],aligned_common_center_ratio=common_grid['outside_ratio'],
                old_frozen_ratio_abs_diff=abs(r['outside_main_disk_ratio']-sources[w,'pad2'][2]['outside_main_disk_ratio']),
                common_center_abs_diff=abs(m['outside_ratio']-common_base['outside_ratio']),
                aligned_common_center_abs_diff=abs(common_grid['outside_ratio']-common_base['outside_ratio']),
                interpretation='仅分解评价盘掩模/像元积分敏感性，未改变原0.1门；细网格另混入高度重新采样'))
            comparisons.append(dict(wavelength_nm=w,condition=tag,reference='OPEN_FRESNEL_CZT',
                ROI_normalized_L1=float(abs(p-q).sum()),absolute_ROI_L1=float(abs(aligned-ref).sum()),
                collected_energy_difference=float(raw.sum()*(coords[1]-coords[0])**2-ref.sum()),
                interpolated_peak_shift_um=float(np.hypot(loc['x_um']-ref_center[0],loc['y_um']-ref_center[1])),
                reference_x_um=ref_center[0],reference_y_um=ref_center[1],
                reference_outside_ratio=ref_m['outside_ratio'],reference_energy_incident=ref_m['roi_energy_incident'],
                maximum_quartic_phase_bound_roi_rad=meta['maximum_quartic_phase_error_bound_rad'],
                formal_gate=None,reason='非周期近轴积分有独立边界；与精确ASM的差同时含近轴误差、采样及有限域误差，不能直接互相替代'))
    csvwrite(out/'diagnostics/domain_sweep.csv',domain)
    csvwrite(out/'diagnostics/independent_propagator_comparison.csv',comparisons)
    csvwrite(out/'diagnostics/ratio_sensitivity_decomposition.csv',ratios)
    # RS仅求关键点局部阵列；离轴尾部是稀疏抽样，不能拿来认证全边界积分。
    for w in [420,425,546.1,660]:
        start=time.perf_counter();u,_=input_field(d,h,w,cfg)
        raw,c,r=sources[w,'pad2'];rr,cc=np.unravel_index(raw.argmax(),raw.shape)
        yy,xx=np.meshgrid(c[rr-3:rr+4],c[cc-3:cc+4],indexing='ij')
        point=np.column_stack([xx.ravel(),yy.ravel()]);kind=['core_native_grid']*len(point)
        if w==425:
            ref,c2,_=references[w];loc=interpolate(ref,c2,3,starts=4)
            fine=np.arange(-6,7)*.25
            yy,xx=np.meshgrid(fine+loc['y_um'],fine+loc['x_um'],indexing='ij')
            point=np.vstack([point,np.column_stack([xx.ravel(),yy.ravel()])]);kind+=['core_fine_quarter_um']*(13*13)
        tail=np.array([[sign*x,.5] for x in [512.5,1024.5,2040.5,4088.5,5112.5] for sign in [-1,1]])
        point=np.vstack([point,tail]);kind+=['tail_sparse_point']*len(tail)
        val=rs_points(u,d['coord'],point,w,cfg['sensor_mm']);intensity=abs(val)**2
        npz(out/'propagation'/f'RS_points_{w:g}nm.npz',points_um=point,field_without_global_piston=val,intensity_raw=intensity,
            point_kind=np.asarray(kind),height_array_sha256=arrsha(h),wavelength_nm=w)
        ref,c2,_=references[w]
        for i,((x,y),k,truth) in enumerate(zip(point,kind,intensity)):
            row=dict(wavelength_nm=w,kind=k,x_um=x,y_um=y,RS_intensity_raw=float(truth),
                pupil_quadrature_pitch_um=1.,local_kernel_frequency_cyc_per_um=float(abs(x)/np.sqrt(x*x+y*y+(cfg['sensor_mm']*1000)**2)/(w/1000)),
                sampling_warning=bool(abs(x)/np.sqrt(x*x+y*y+(cfg['sensor_mm']*1000)**2)/(w/1000)>.45),
                reason='RS中点求和是非周期标量参考，未认证输入像元内部高度；远端接近Nyquist需另行细分求积')
            if k.startswith('core'):
                row['fresnel_interpolated_intensity']=float(map_coordinates(ref,[[y+255.5],[x+255.5]],order=3,mode='nearest')[0])
                for tag in ['pad2','pad4','pad5']:
                    if (w,tag) in sources:
                        a,coord,_=sources[w,tag]
                        row[f'ASM_{tag}_interpolated_intensity']=float(map_coordinates(a,[[y+255.5],[x+255.5]],order=3,mode='nearest')[0])
            elif (w,'pad5') in sources and abs(x)<5120:
                path=out/'propagation'/f'ASM_pad5_{w:g}nm.npz'
                with np.load(path,allow_pickle=False) as z:prof=z['full_domain_y05um_profile_raw']
                ix=int(round(x+5119.5));row['ASM_pad5_profile_intensity']=float(prof[ix])
            rsrows.append(row)
        event(out,event='RS_DIRECT_COMPLETE',wavelength_nm=w,points=len(point),seconds=time.perf_counter()-start,resource=memory())
        print(f'RS开放边界 {w:g}nm {len(point)}点 {time.perf_counter()-start:.2f}s',flush=True)
    csvwrite(out/'diagnostics/RS_point_comparison.csv',rsrows)
    summary=[]
    for w in [420,425,546.1,660]:
        rr=[r for r in rsrows if r['wavelength_nm']==w and r['kind']=='core_native_grid']
        truth=np.array([r['RS_intensity_raw'] for r in rr])
        for method,key in [('OPEN_FRESNEL','fresnel_interpolated_intensity'),('pad2','ASM_pad2_interpolated_intensity'),('pad4','ASM_pad4_interpolated_intensity'),('pad5','ASM_pad5_interpolated_intensity')]:
            if key not in rr[0]:continue
            values=np.array([r[key] for r in rr]);summary.append(dict(wavelength_nm=w,method=method,
                core49_relative_L1=float(abs(values-truth).sum()/truth.sum()),
                core49_max_error_relative_peak=float(abs(values-truth).max()/truth.max()),
                note='7x7局部同原生1um坐标；RS与CZT无周期延拓；不是整ROI精确RS积分'))
    csvwrite(out/'diagnostics/RS_core_error_summary.csv',summary)
    # 每种估计器/域逐1nm并行结果，不由新估计器授予旧G2通过。
    trajectories=[]
    for w in range(420,431):
        for tag in ['pad2','pad4','OPEN_FRESNEL']:
            item=references[w] if tag=='OPEN_FRESNEL' else sources.get((w,tag))
            if item is None:continue
            a,c,r=item
            for name,loc in [('frozen3',quadratic(a,c)),('cubic_diagnostic',interpolate(a,c,3,starts=4))]:
                trajectories.append(dict(wavelength_nm=w,condition=tag,locator=name,x_um=loc['x_um'],y_um=loc['y_um'],
                    angle_deg=float(np.rad2deg(np.arctan2(loc['y_um'],loc['x_um']))),fit_valid=loc['fit_valid'],
                    halfmax_components=int(label(a>=.5*a.max())[1]),diagnostic_only=True))
    for tag in ['pad2','pad4','OPEN_FRESNEL']:
        for loc in ['frozen3','cubic_diagnostic']:
            rr=[r for r in trajectories if r['condition']==tag and r['locator']==loc]
            angles=np.rad2deg(np.unwrap(np.deg2rad([r['angle_deg'] for r in rr])))
            for i,(r,ang) in enumerate(zip(rr,angles)):
                r['diagnostic_unwrapped_deg']=float(ang);r['delta_angle_deg']=float(angles[i]-angles[i-1]) if i else None
                r['old_scaled_04_18_gate']=.4<=r['delta_angle_deg']<=1.8 if i else None
    csvwrite(out/'diagnostics/blue_domains_trajectory.csv',trajectories)
    textfile(out/'diagnostics/boundary_metric_definition.md','''# 全域16um边界份额定义

冻结源码：experiments/n02/optics.py propagate，b=round(16/dx)。
分子：I[:b,:]+I[-b:,:]+I[b:-b,:b]+I[b:-b,-b:]之和乘dx²；四角只计一次。
分母：整个填充传播数组ΣI dx²。原字段edge_fraction，本轮并列boundary_share_16um。
坐标原点在几何中心，像素(i-(N-1)/2)dx。标准输入2048um，pad2输出4096um、pad4输出8192um、pad5输出10240um；ROI始终512um。
dx0.5的旧输入4096像素仍2048um，pad2输出8192像素=4096um，条带32像素。它增加采样，不增加物理域。
条带面积=4Db-4b²，其中D为全域物理宽度，b=16um；不同D的面积与测量位置都不同，条带份额下降不是环绕误差的直接测量。
ROI外能量=有限域总能量-512um ROI能量；光学主瓣效率=主盘能量/入瞳能量，均不是上述边界指标。
原checks.edge=max(candidate_edge,frozen_baseline_edge)<0.001；基线超门时，候选达标也不能改变组合FAIL。本轮逐列保留candidate_edge、frozen_baseline_edge、combined_gate。
原0.001门永久保留；0.0005/0.001/0.002仅作敏感性图，不改变验收。
''')
    thresholds=[]
    for r in domain:
        for t in [.0005,.001,.002]:thresholds.append(dict(wavelength_nm=r['wavelength_nm'],condition=r['condition'],diagnostic_threshold=t,
             candidate_pass=r['candidate_edge']<t,combined_pass=max(r['candidate_edge'],r['frozen_baseline_edge'])<t,
             official_threshold_unchanged=.001))
    csvwrite(out/'diagnostics/boundary_threshold_sensitivity.csv',thresholds)
    plot_b(out,domain,comparisons,summary)
    return sources,references,domain,comparisons,ratios,summary,trajectories


def plot_b(out,domain,comparisons,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(17,5),layout='constrained')
    for w in [420,425,430,546.1,660]:
        rr=sorted([r for r in domain if r['wavelength_nm']==w and r['condition']!='dx05'],key=lambda r:r['physical_width_um'])
        axes[0].plot([r['physical_width_um'] for r in rr],[r['candidate_edge'] for r in rr],'o-',label=f'{w:g}nm')
        axes[1].plot([r['physical_width_um'] for r in rr],[r['roi_energy_incident'] for r in rr],'o-')
    axes[0].axhline(.001,color='red',label='frozen 0.001');axes[0].set(xlabel='Physical domain width (um)',ylabel='16um boundary / finite domain');axes[0].legend(fontsize=7)
    axes[1].set(xlabel='Physical domain width (um)',ylabel='Fixed 512um ROI / incident')
    for method in sorted(set(r['method'] for r in summary)):
        rr=[r for r in summary if r['method']==method];axes[2].semilogy([r['wavelength_nm'] for r in rr],[r['core49_relative_L1'] for r in rr],'o-',label=method)
    axes[2].set(xlabel='Wavelength (nm)',ylabel='Core 7x7 L1 relative to direct RS');axes[2].legend(fontsize=7)
    fig.suptitle('N02-1C-R / fixed B2 height / old gates retained / p0b_boundary.py')
    fig.savefig(out/'diagnostics/domain_sweep.png',dpi=150);plt.close(fig)
