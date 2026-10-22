"""旧原始数组的独立审计与A/C工作包，不触发结构设计或优化。"""
from p0b_common import *
from p0b_locators import quadratic,centroid,all_locators,synthetic_tests
from scipy.ndimage import maximum_filter,label


def audit(out):
    write(out/'preservation_before.json',snapshot())
    textfile(out/'git_status_before.txt',git('status','--short'))
    textfile(out/'task_original.md',TASK.read_text(encoding='utf-8'))
    inputs={TASK.as_posix():sha(TASK)}
    manifest=read(OLD/'artifact_manifest.json')
    for name,digest in manifest.items():
        p=OLD/name;actual=sha(p);assert actual==digest,f'冻结产物SHA不一致：{p}'
        inputs[p.as_posix()]=actual
    for p in list((ROOT/'experiments/n02').glob('*.py'))+[OLD/'manifest.json',OLD/'artifact_manifest.json']+list((ROOT/'reports/n02/n02_20261019_02').glob('*.md')):
        inputs[p.as_posix()]=sha(p)
    write(out/'input_hashes.json',inputs)
    evidence=read(OLD/'artifact_verification.json');errors=[];max_area=0.;max_normal=0.
    for row in evidence['cases']:
        p=OLD/row['path'];raw,c,r=loadcase(p);dx=float(c[1]-c[0])
        area=abs(float(raw.sum()*dx*dx)-r['crop_energy']);max_area=max(max_area,area)
        with np.load(p,allow_pickle=False) as z:err=float(abs(z['normalized_psf']-raw/raw.sum()).max())
        max_normal=max(max_normal,err)
        if area>1e-12 or err>1e-15 or not np.isfinite(raw).all() or raw.min()<0:errors.append(str(p))
    assert not errors
    gates=read(OLD/'gates.json');tests=read(OLD/'physics_tests.json')
    assert len(tests)==12 and all(t['status']=='PASS' for t in tests)
    assert gates['G0']['status']==gates['G1']['status']=='PASS' and gates['G2']['status']==gates['G3_Numerics']['status']=='FAIL'
    assert all(gates[g]['execution']=='NOT_TESTED' for g in ['G4','G5','G6','G7','G8'])
    write(out/'legacy_gate_preservation.json',dict(old_gates_sha256=sha(OLD/'gates.json'),unchanged_old_labels=gates,
        physics_tests_count=len(tests),physics_tests_pass_count=sum(t['status']=='PASS' for t in tests),
        artifact_hash_checked=len(manifest),raw_npz_reread=len(evidence['cases']),max_area_error=max_area,max_normalized_error=max_normal,
        note='原gates.json固定PASS写法不能替代此处回读证据；本轮不重新给旧门授予PASS'))
    cfg,h,d=pupil();std=csvread(OLD/'B2/standard_metrics.csv');links=csvread(OLD/'B2/standard_links.csv')
    actual=[]
    for row in std:
        w=float(row['wavelength_nm']);raw,c,r=loadcase(OLD/'B2/cases'/f'{w:g}nm.npz')
        q=quadratic(raw,c);im=independent_metrics(raw,c,w,cfg,(q['x_um'],q['y_um']))
        re=old.measure(raw,c,r,cfg,w)
        assert im['halfmax_components']==int(row['halfmax_components'])
        assert abs(im['outside_ratio']-float(row['outside_main_disk_ratio']))<1e-12
        assert abs(im['main_disk_energy_incident']-float(row['main_lobe_energy_fraction']))<1e-12
        assert q['fit_valid']==r['subpixel_fit'] and re['n02_status']==row['n02_status']
        actual.append(dict(wavelength_nm=w,n02_status=re['n02_status'],angle_deg=float(np.rad2deg(np.arctan2(q['y_um'],q['x_um']))),**im))
    angle=np.rad2deg(np.unwrap(np.deg2rad([r['angle_deg'] for r in actual])))
    canonical=dict(height_max_um=float(h.max()),standard_valid=sum(r['n02_status']=='PASS' for r in actual),
        independent_rotation_deg=float(angle[-1]-angle[0]),unique_links=sum(r['main_link_unique']=='True' for r in links),
        oldcsv_max_height_um=float(std[0]['max_height_um']),oldcsv_last_unwrapped_deg=float(std[-1]['unwrapped_angle_deg']),
        roi_min=min(r['roi_energy_incident'] for r in actual),roi_max=max(r['roi_energy_incident'] for r in actual),
        main_min=min(r['main_disk_energy_incident'] for r in actual),old_edge_420=float(std[0]['edge_fraction']),old_edge_660=float(std[-1]['edge_fraction']),
        height_array_sha256=arrsha(h),height_file_sha256=sha(OLD/'B2/height_um.npy'))
    assert canonical['standard_valid']==25 and canonical['unique_links']==24
    csvwrite(out/'diagnostics/legacy_standard_recalculation.csv',actual)
    write(out/'diagnostics/legacy_numbers_rechecked.json',canonical)
    conv=read(OLD/'gate3_convergence.json');breakdown=[]
    for r in conv:
        w=r['wavelength_nm'];condition=r['condition'];_,_,baseline=loadcase(OLD/'B2/cases'/f'{w:g}nm.npz')
        name='cpu_asm' if condition=='independent_cpu_ASM' else condition
        _,_,rec=loadcase(OLD/'convergence/cases'/f'{name}_{w:g}nm.npz')
        combined=max(rec['edge_fraction'],baseline['edge_fraction'])<.001
        assert combined==r['checks']['edge']
        breakdown.append(dict(wavelength_nm=w,condition=condition,candidate_edge=rec['edge_fraction'],frozen_baseline_edge=baseline['edge_fraction'],
            candidate_edge_gate=rec['edge_fraction']<.001,baseline_edge_gate=baseline['edge_fraction']<.001,combined_gate=combined,
            outside_ratio_abs_change=r['outside_ratio_abs_diff'],outside_ratio_gate=r['checks']['main_ratio'],
            all_failed_checks=[k for k,v in r['checks'].items() if not v],original_status=r['status'],
            required=condition in ['pad4','dx05','independent_cpu_ASM']))
    required=[r for r in breakdown if r['required']]
    csvwrite(out/'diagnostics/legacy_convergence_failure_breakdown.csv',breakdown)
    write(out/'diagnostics/legacy_convergence_count.json',dict(required=len(required),fail=sum(r['original_status']=='FAIL' for r in required),
        passed=sum(r['original_status']=='PASS' for r in required),non_edge_failures=[r for r in required if not r['outside_ratio_gate']],
        correction='上轮聊天中“主峰位置、角度和归一化形态差在容差内”不代表全部非边缘指标通过；660nm pad4和546.1nm dx0.5主盘外比均超0.1。'))
    env=dict(time=now(),python=sys.executable,python_version=sys.version,platform=platform.platform(),numpy=np.__version__,scipy=scipy.__version__,
        torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),git_head=git('rev-parse','HEAD').strip(),memory=memory(),seed=20261020)
    write(out/'environment.json',env)
    return cfg,h,d,env


def analyze_a(out):
    rows=[];fit425=[];data={};shape=[]
    for w in range(420,431):
        raw,c,r=loadcase(OLD/'B2/cases'/f'{w}nm.npz');data[w]=(raw,c,r)
        locs=all_locators(raw,c)
        cov=centroid(raw,c)['shape_covariance_um2']
        for loc in locs:
            loc.update(wavelength_nm=w,dataset='frozen_dx1_pad2',radius_um=float(np.hypot(loc['x_um'],loc['y_um'])),
                angle_deg=float(np.rad2deg(np.arctan2(loc['y_um'],loc['x_um']))),
                frozen_n01_status=r['n01_status'],halfmax_components=r['halfmax_components'],distinct_side_ratio=r['distinct_side_ratio'])
            rows.append(loc)
            if w==425:fit425.append(loc)
        shape.append(dict(wavelength_nm=w,main_intensity=r['main_peak'],distinct_side_intensity=r['distinct_side_peak'],halfmax_components=r['halfmax_components'],
            strongest_competitor_ratio=1/r['distinct_side_ratio'],radius_frozen_um=r['peak_radius_um'],local_covariance_um2=cov))
    # 补齐旧pad4、细网格的独立冻结拟合核对，保留无约束驻点而非只看PASS。
    for name,path in [('pad4',OLD/'convergence/cases/pad4_425nm.npz'),('dx05',OLD/'convergence/cases/dx05_425nm.npz')]:
        raw,c,r=loadcase(path);q=quadratic(raw,c);q.update(wavelength_nm=425,dataset=name);fit425.append(q)
    hist=csvread(OLD/'425nm_fit_diagnostics.csv')
    for q,ref in zip([fit425[0],fit425[-2],fit425[-1]],hist):
        assert np.allclose(q['unconstrained_offset_pixels'],json.loads(ref['offset_pixels']),atol=1e-12,rtol=0)
        assert np.allclose(q['hessian_eigenvalues'],json.loads(ref['hessian_eigenvalues']),atol=1e-12,rtol=0)
    csvwrite(out/'diagnostics/425_fit_audit.csv',fit425)
    csvwrite(out/'diagnostics/blue_1nm_shape.csv',shape)
    for locator in sorted(set(r['locator'] for r in rows)):
        subset=[r for r in rows if r['locator']==locator];angle=np.rad2deg(np.unwrap(np.deg2rad([r['angle_deg'] for r in subset])))
        previous=None
        for i,(r,a) in enumerate(zip(subset,angle)):
            r['diagnostic_unwrapped_deg']=float(a);r['delta_angle_deg']=float(angle[i]-angle[i-1]) if i else None
            r['spatial_displacement_um']=float(np.hypot(r['x_um']-previous['x_um'],r['y_um']-previous['y_um'])) if previous else None
            r['scaled_04_18_gate']=.4<=r['delta_angle_deg']<=1.8 if i else None
            previous=r
    uncertainty=[]
    for w in range(420,431):
        ss=[r for r in rows if r['wavelength_nm']==w and r['locator'] in ['constrained_log5','constrained_log7','interpolation_order3']]
        xy=np.array([[r['x_um'],r['y_um']] for r in ss]);mean=xy.mean(axis=0);radius=np.linalg.norm(mean)
        cov=np.cov(xy.T,ddof=1);tangent=np.array([-mean[1],mean[0]])/radius
        sigma_xy=float(np.sqrt(np.trace(cov)));sigtheta=float(np.rad2deg(np.sqrt(max(0,tangent@cov@tangent))/radius))
        uncertainty.append(dict(wavelength_nm=w,estimator_centroid_x_um=mean[0],estimator_centroid_y_um=mean[1],
            inter_estimator_position_rms_um=sigma_xy,sigma_theta_proxy_deg=sigtheta,
            maximum_locator_separation_um=float(np.max(np.linalg.norm(xy[:,None,:]-xy[None,:,:],axis=-1))),
            reason='仅估计器离散度传播：sigma_theta²=t^T Cov(x,y)t/r²；不是统计噪声标定，系统偏差可能相关'))
        for r in rows:
            if r['wavelength_nm']==w:r['sigma_theta_proxy_deg']=sigtheta
    csvwrite(out/'diagnostics/blue_1nm_trajectory_comparison.csv',rows)
    csvwrite(out/'diagnostics/blue_position_uncertainty.csv',uncertainty)
    tests=synthetic_tests();write(out/'diagnostics/locator_synthetic_tests.json',dict(seed=20261020,rows=tests,
       scope='8种已知解析峰/噪声，共6定位器；约束法不会产生>1pixel，须看边界活跃及真实位置误差，不以限幅证明准确'))
    synthetic_rows=[{k:r.get(k) for k in ['case','locator','position_error_um','fit_valid','failure_reason','unconstrained_offset_pixels','boundary_active','noise']} for r in tests]
    csvwrite(out/'diagnostics/locator_synthetic_tests.csv',synthetic_rows)
    plot_a(out,data,rows,fit425)
    return rows,uncertainty,fit425


def plot_a(out,data,rows,fit425):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    raw,c,r=data[425];rr,cc=np.unravel_index(raw.argmax(),raw.shape)
    fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained')
    for col,width in enumerate([3,5,7]):
        h=width//2;p=raw[rr-h:rr+h+1,cc-h:cc+h+1]
        ax=axes[0,col];im=ax.imshow(p,origin='lower',extent=[c[cc-h]-.5,c[cc+h]+.5,c[rr-h]-.5,c[rr+h]+.5]);fig.colorbar(im,ax=ax,label='Raw intensity (um^-2)')
        ax.plot(r['peak_x_um'],r['peak_y_um'],'rx',label='frozen fallback')
        q=fit425[0];delta=q['unconstrained_offset_pixels'];ax.plot(c[cc]+delta[0],c[rr]+delta[1],'c+',label='unbounded stationary')
        ax.set(title=f'425nm / {width}x{width} raw',xlabel='x (um)',ylabel='y (um)');ax.legend(fontsize=7)
        axes[1,col].plot(c[cc-h:cc+h+1],p[h],'o-',label='y=-21.5um row');axes[1,col].set(xlabel='x (um)',ylabel='Raw intensity (um^-2)',title=f'{width}x{width} horizontal cut');axes[1,col].legend()
        npz(out/'diagnostics'/f'425_local_{width}.npz',raw=p,coords_x_um=c[cc-h:cc+h+1],coords_y_um=c[rr-h:rr+h+1])
    fig.suptitle('N02-1C-R / frozen B2 dx1um pad2 / independent fit audit / p0b_analysis.py')
    fig.savefig(out/'diagnostics/425_local_psf.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(17,5),layout='constrained')
    for name in sorted(set(r['locator'] for r in rows)):
        rr=[r for r in rows if r['locator']==name]
        axes[0].plot([r['wavelength_nm'] for r in rr],[r['angle_deg'] for r in rr],'o-',label=name)
        axes[1].plot([r['wavelength_nm'] for r in rr][1:],[r['delta_angle_deg'] for r in rr][1:],'o-')
        axes[2].plot([r['x_um'] for r in rr],[r['y_um'] for r in rr],'o-')
    axes[0].set(xlabel='Wavelength (nm)',ylabel='Angle (deg)',title='Parallel locators; frozen FAIL retained');axes[0].legend(fontsize=7)
    axes[1].axhline(.4,color='gray');axes[1].axhline(1.8,color='gray');axes[1].set(xlabel='Wavelength (nm)',ylabel='Delta angle / 1nm (deg)')
    axes[2].set(xlabel='x (um)',ylabel='y (um)',title='Brightest local branch, not global mode proof')
    fig.suptitle('B2 / 420:1:430nm / same raw ROI / p0b_analysis.py')
    fig.savefig(out/'diagnostics/blue_locator_trajectories.png',dpi=150);plt.close(fig)


def gram_diagnostics(columns):
    X=np.stack(columns,axis=1);X=X/np.linalg.norm(X,axis=0)
    gram=X.T@X;raw_eig=np.linalg.eigvalsh(gram);eig=np.maximum(raw_eig,0);p=eig/eig.sum()
    tol=float(len(eig)*np.finfo(float).eps*eig.max());positive=eig>tol
    singular=np.linalg.svd(X,compute_uv=False)
    return gram,raw_eig,dict(effective_rank=float(np.exp(-np.sum(p[p>0]*np.log(p[p>0])))),
        gram_condition=float(eig[-1]/eig[0]) if eig[0]>0 else None,
        rank_at_eps_n_lambda_max=int(positive.sum()),threshold=tol,
        raw_negative_eigenvalues=int(np.sum(raw_eig<0)),svd_gram_condition=float((singular[0]/singular[-1])**2),
        svd_eigenvalue_max_difference=float(np.max(abs(singular[::-1]**2-raw_eig))))


def analyze_c(out,cfg):
    energy=[];pixelrows=[];gramrows=[];cols={p:[] for p in [1,2,4,8]};eta=[]
    oldpixels={(int(r['pixel_um']),float(r['wavelength_nm'])):r for r in csvread(OLD/'gate3_pixel_integration.csv')}
    for w in range(420,661,10):
        raw,c,r=loadcase(OLD/'B2/cases'/f'{w}nm.npz')
        q=quadratic(raw,c);m=independent_metrics(raw,c,w,cfg,(q['x_um'],q['y_um']))
        roi=float(raw.sum());eta.append(roi)
        energy.append(dict(wavelength_nm=w,incident_pupil_energy=r['input_energy'],finite_periodic_domain_energy=r['raw_energy'],
            roi_energy_incident=roi,roi_fraction_finite_domain=roi/r['raw_energy'],outside_roi_finite_energy=r['raw_energy']-roi,
            main_disk_energy_incident=m['main_disk_energy_incident'],main_disk_fraction_roi=m['main_disk_fraction_roi'],
            ROI_normalized_sum=float(np.sum(raw/raw.sum())),area_factor_um2=1.,
            old_main_difference=m['main_disk_energy_incident']-r['main_lobe_energy_fraction'],
            infinite_space_collection_efficiency=None,reason='有限周期域不是无限空间；本轮未加入反射/吸收/真实探测器响应'))
        for pixel in [1,2,4,8]:
            n=512//pixel;a=raw.reshape(n,pixel,n,pixel).mean(axis=(1,3));coord=(np.arange(n)-(n-1)/2)*pixel
            loc=quadratic(a,coord);center=(loc['x_um'],loc['y_um']);metrics=independent_metrics(a,coord,w,cfg,center)
            ref=oldpixels[pixel,float(w)]
            assert abs(metrics['roi_energy_incident']-float(ref['energy_sum']))<1e-12
            pixelrows.append(dict(pixel_um=pixel,wavelength_nm=w,peak_x_um=center[0],peak_y_um=center[1],peak_radius_um=float(np.hypot(*center)),
                fit_valid=loc['fit_valid'],angle_deg=float(np.rad2deg(np.arctan2(center[1],center[0]))),
                old_angle_difference_deg=float((np.rad2deg(np.arctan2(center[1],center[0]))-float(ref['angle_deg'])+180)%360-180),
                pixel_integration_energy_error=metrics['roi_energy_incident']-roi,
                old_n02_status=ref['n02_status'],**metrics))
            cols[pixel].append(a.ravel())
    csvwrite(out/'diagnostics/energy_accounting.csv',energy)
    csvwrite(out/'diagnostics/pixel_integration_effect.csv',pixelrows)
    spectra=[]
    for pixel,vectors in cols.items():
        gram,eig,s=gram_diagnostics(vectors)
        oldgram=np.load(OLD/(f'pixel_{pixel}um_gram.npz' if pixel!=1 else 'B2/standard_gram.npz'),allow_pickle=False)['gram']
        err=float(abs(gram-oldgram).max());assert err<1e-12
        weights=np.sqrt(10000*np.array(eta));weighted=weights[:,None]*gram*weights[None,:]
        we=np.linalg.eigvalsh(weighted);wp=np.maximum(we,0);wp/=wp.sum()
        wrank=float(np.exp(-np.sum(wp[wp>0]*np.log(wp[wp>0]))))
        gramrows.append(dict(pixel_um=pixel,max_old_gram_difference=err,**s,
            photon_weighted_gram_condition=float(we[-1]/we[0]) if we[0]>0 else None,photon_weighted_effective_rank=wrank))
        for i,e in enumerate(eig):spectra.append(dict(pixel_um=pixel,eigenvalue_index=i,raw_eigenvalue=e,weighted_eigenvalue=we[i],clipped_for_entropy=max(e,0)))
        npz(out/'diagnostics'/f'gram_pixel{pixel}um.npz',gram=gram,raw_eigenvalues=eig,photon_weighted_gram=weighted,weighted_eigenvalues=we,
            wavelength_nm=np.arange(420,661,10),incident_photons_per_pure_channel=10000.,collected_photons_per_channel=np.array(eta)*10000)
    csvwrite(out/'diagnostics/gram_summary.csv',gramrows);csvwrite(out/'diagnostics/gram_eigenvalue_spectrum.csv',spectra)
    write(out/'diagnostics/work_C_checks.json',dict(max_main_energy_old_difference=max(abs(r['old_main_difference']) for r in energy),
        pixel_integrations=100,max_pixel_energy_error=max(abs(r['pixel_integration_energy_error']) for r in pixelrows),gram_summaries=gramrows))
    textfile(out/'diagnostics/gram_definition_and_spectrum.md',f'''# 强度字典与像元口径

SIMULATED：仅回读原始25通道，不做G7/G8或场景重建。
令I_k为512um ROI强度，dx²为面积，η_k=ΣI_k dx²，入瞳归一能量1。
ROI概率质量为I_k dx²/η_k；主盘入瞳份额为Σ_disk I_k dx²；主盘/ROI是另一比例。
列L2归一X_k=vec(I_k)/||vec(I_k)||₂，G=XᵀX，未去均值。
原始特征值保留CSV；仅为熵将负值截0，p_i=max(λ_i,0)/Σmax(λ_i,0)，有效秩exp(-Σp_i ln p_i)。
代数秩阈值K eps λmax另报，不能把有效秩当代数秩。原条件数λmax/λmin，λmin≤0时报null及原因，不用极小数冒充可逆；独立SVD复核平方条件数。
像元1/2/4/8um为方形100%填充，块平均强度后乘pixel²积分，固定ROI不变；并非真实MTF。
光子权重ASSUMED：每个纯谱字典列有10000入瞳光子，η_k来自单位入瞳ROI，Dkk=sqrt(10000η_k)，G_photon=DGD。
这只是列可信度/收集权重诊断，不是Poisson FIM，不对应未知混合谱下的完整噪声协方差，也不是双孔径失败证明。对每列重新L2归一会消掉权重，所以必须同时保留G与DGD。
独立1um条件数={gramrows[0]['gram_condition']:.9f}，有效秩={gramrows[0]['effective_rank']:.9f}，光子权重后条件数={gramrows[0]['photon_weighted_gram_condition']:.9f}。
所有4组Gram与原产物最大差≤1e-12，详见gram_summary.csv；没有真实MTF、噪声标定、吸收反射数据。
''')
    plot_c(out,energy,pixelrows,gramrows,spectra)
    return energy,pixelrows,gramrows


def plot_c(out,energy,pixelrows,gramrows,spectra):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,3,figsize=(16,5),layout='constrained')
    ax[0].plot([r['wavelength_nm'] for r in energy],[r['roi_energy_incident'] for r in energy],label='ROI / incident')
    ax[0].plot([r['wavelength_nm'] for r in energy],[r['main_disk_energy_incident'] for r in energy],label='main disk / incident');ax[0].legend()
    ax[0].set(xlabel='Wavelength (nm)',ylabel='Energy fraction')
    for p in [1,2,4,8]:
        rr=[r for r in pixelrows if r['pixel_um']==p];ax[1].plot([r['wavelength_nm'] for r in rr],[r['peak_radius_um'] for r in rr],label=f'{p}um')
        ss=[r for r in spectra if r['pixel_um']==p];ax[2].semilogy([r['eigenvalue_index'] for r in ss],[max(r['raw_eigenvalue'],1e-16) for r in ss],label=f'{p}um')
    ax[1].set(xlabel='Wavelength (nm)',ylabel='Frozen-estimator radius (um)');ax[1].legend()
    ax[2].set(xlabel='Eigenvalue index (ascending)',ylabel='Intensity Gram eigenvalue');ax[2].legend()
    fig.suptitle('N02-1C-R / same frozen B2 raw PSFs / ideal pixel integration / p0b_analysis.py')
    fig.savefig(out/'diagnostics/energy_pixel_gram.png',dpi=150);plt.close(fig)
