"""数值收敛、独立复算及明确假设的加工/材料扰动。"""
import sys
sys.dont_write_bytecode=True
import json
import math
import numpy as np
from scipy.ndimage import gaussian_filter, shift
from optics import *
from audit import write, textfile
from evaluate import csvwrite, load, evaluate


def comparison(raw, r, ref, rr, cfg):
    # 相同物理视场，细网格按2×2像元面积平均到1um；原始强度不重归一。
    aligned=raw
    if raw.shape[0]==2*ref.shape[0]:
        n=ref.shape[0];aligned=raw.reshape(n,2,n,2).mean(axis=(1,3))
    p=aligned/aligned.sum();q=ref/ref.sum()
    l1=float(np.abs(p-q).sum())
    xy=math.hypot(r['peak_x_um']-rr['peak_x_um'],r['peak_y_um']-rr['peak_y_um'])
    angle=abs((r['raw_angle_deg']-rr['raw_angle_deg']+180)%360-180)
    ratio=abs(r['outside_main_disk_ratio']-rr['outside_main_disk_ratio'])
    disk=abs(r['main_lobe_energy_fraction']-rr['main_lobe_energy_fraction'])
    checks=dict(shape=l1<.05,position=xy<2.,angle=angle<3.,edge=max(r['edge_fraction'],rr['edge_fraction'])<.001,
                main_ratio=ratio<.10,main_energy=disk<.01,energy_accounting=r['spectral_energy_accounting_error']<(1e-5 if r['precision']==64 else 1e-10))
    return dict(shape_l1=l1,peak_shift_um=xy,angle_diff_deg=angle,outside_ratio_abs_diff=ratio,
        main_incident_fraction_abs_diff=disk,roi_fraction_diff=r['crop_fraction']-rr['crop_fraction'],
        raw_aligned_l1=float(np.abs(aligned-ref).sum()),edge_fraction=r['edge_fraction'],
        status='PASS' if all(checks.values()) else 'FAIL',checks=checks),aligned


def validate(out,cfg):
    runner=module('n02_runner_validation',Path(__file__).with_name('run.py'))
    make_folder,acquire_case,STANDARD,save_case,event=(getattr(runner,n) for n in ['make_folder','acquire_case','STANDARD','save_case','event'])
    base=out/'B2';h=np.load(base/'height_um.npy');h.setflags(write=False)
    d=design(cfg)
    summary=json.loads((base/'standard_summary.json').read_text(encoding='utf-8'))
    dense_failures=json.loads((base/'dense_blue_summary.json').read_text(encoding='utf-8'))['failure_wavelengths_nm']
    standard_records=[load(base/'cases'/f'{w:g}nm.npz')[2] for w in STANDARD]
    worst=[r['wavelength_nm'] for r in sorted(standard_records,key=lambda r:r['outside_main_disk_ratio'])[:2]]
    waves=sorted(set([420,546.1,660]+worst+dense_failures[:2]))
    write(out/'gate3_convergence_plan.json',dict(wavelengths_nm=waves,selected_worst_nm=worst,
        protocol='protocol_frozen.json',alignment='0.5um强度按2x2面积均值到1um；不配准平移；能量单独物理积分',
        precision='complex64对照仅诊断；最终证据使用complex128；独立SciPy使用去除全局活塞的精确ASM',
        fine_sampling='同一连续解析设计重新采样量化，不插值包裹高度图；物理输入视场2048um不变'))
    folder=out/'convergence';(folder/'cases').mkdir(parents=True,exist_ok=False)
    rows=[];diffs=[]
    for w in waves:
        ref,c,rr=load(base/'cases'/f'{w:g}nm.npz')
        for label,changes,options in [('pad4',dict(padding=4),{}),('dx05',dict(size=4096,pitch_um=.5),{}),
                                      ('complex64',{},dict(precision=64)),('Fresnel',{},dict(method='Fresnel'))]:
            cc=dict(cfg,**changes,candidate_id=f'B2_{label}')
            dd=design(cc) if label=='dx05' else d
            hh=dd['height'] if label=='dx05' else h
            event(out,event='START',candidate=cc['candidate_id'],wavelength_nm=w,config=cc,options=options)
            raw,coord,r=propagate(dd,hh,w,cc,**options)
            save_case(folder/'cases'/f'{label}_{w:g}nm.npz',raw,coord,r)
            comp,aligned=comparison(raw,r,ref,rr,cc)
            comp.update(condition=label,wavelength_nm=w,seconds=r['seconds'],gpu_peak_bytes=r.get('gpu_peak_allocated_bytes'))
            rows.append(comp)
            diffs.append((label,w,aligned-ref))
            print(f"收敛 {label} {w:g}nm {comp['status']} L1={comp['shape_l1']:.5g} shift={comp['peak_shift_um']:.5g} angle={comp['angle_diff_deg']:.5g}",flush=True)
            event(out,event='COMPLETE',candidate=cc['candidate_id'],wavelength_nm=w,status=comp['status'],seconds=r['seconds'])
            if label=='dx05':del dd,hh
        # 独立CPU精确实现仅对三关键点复算，限制资源。
        if w in [420,546.1,660]:
            cc=dict(cfg,device='cpu_scipy',candidate_id='B2_CPU_ASM')
            raw,coord,r=propagate(d,h,w,cc)
            save_case(folder/'cases'/f'cpu_asm_{w:g}nm.npz',raw,coord,r)
            comp,aligned=comparison(raw,r,ref,rr,cc)
            comp.update(condition='independent_cpu_ASM',wavelength_nm=w,seconds=r['seconds'])
            rows.append(comp)
    csvwrite(out/'gate3_convergence.csv',rows)
    write(out/'gate3_convergence.json',rows)
    required=[r for r in rows if r['condition'] in ['pad4','dx05','independent_cpu_ASM']]
    numerics='PASS' if all(r['status']=='PASS' for r in required) else 'FAIL'
    textfile(out/'gate3_convergence.md',f"# G3 数值收敛\n\nSIMULATED G3-Numerics: **{numerics}**。\n关键判定采用padding4、相同物理视场dx0.5、独立SciPy ASM；complex64和Fresnel近似另列，不能覆盖精确模型失败。\n预注册容差见protocol_frozen.json；逐工况原始PSF及能量见convergence/cases与gate3_convergence.csv。\n形态L1、峰位/角度、主盘外峰比、主瓣入瞳效率、边缘与Parseval门全部报告。ROI99另列而不当作Parseval守恒。\n")
    plot_diffs(out,diffs)
    # Q8/Q16和round均重新采样同一连续设计；缩放与扰动直接作用在固定实体，不再取模。
    variants=[]
    for q,quant in [(10,'round'),(8,'floor'),(16,'floor')]:
        cc=dict(cfg,Q=q,quantizer=quant,candidate_id=f'Q{q}_{quant}')
        dd=design(cc);variants.append((cc['candidate_id'],cc,dd,dd['height'],{},'同一连续设计的独立量化'))
    for scale in [.9,.95,1.05,1.1]:
        name=f'height_scale_{scale:g}';cc=dict(cfg,candidate_id=name)
        hh=np.array(h*scale);hh.setflags(write=False)
        variants.append((name,cc,d,hh,{},f'ASSUMED 全局高度直接缩放{scale:g}，不重包裹'))
    variants.extend([('material_constant',dict(cfg,candidate_id='material_constant'),d,h,dict(material='constant'),'ASSUMED 固定设计折射率'),
        ('n_minus005',dict(cfg,candidate_id='n_minus005'),d,h,dict(n_offset=-.005),'ASSUMED 全谱n减0.005'),
        ('n_plus005',dict(cfg,candidate_id='n_plus005'),d,h,dict(n_offset=.005),'ASSUMED 全谱n加0.005')])
    rng=np.random.default_rng(cfg['seed'])
    noise=gaussian_filter(rng.normal(size=h.shape),sigma=10)
    noise=noise/np.std(noise[d['mask']])*.02
    hh=np.where(d['mask'],np.maximum(0,h+noise),0.)
    variants.append(('local20nm',dict(cfg,candidate_id='local20nm'),d,hh,{},'ASSUMED 10um相关长度、20nm RMS高斯高度误差；负高截为零'))
    for sigma in [.5,1.]:
        hh=np.where(d['mask'],gaussian_filter(h,sigma=sigma),0.)
        name=f'rounding_{sigma:g}um'
        variants.append((name,dict(cfg,candidate_id=name),d,hh,{},f'ASSUMED 高度Gaussian卷积sigma={sigma}um，代表边缘圆角敏感性，不是工艺实测'))
    for px in [2,4]:
        hh=np.repeat(np.repeat(h.reshape(cfg['size']//px,px,cfg['size']//px,px).mean(axis=(1,3)),px,axis=0),px,axis=1)
        hh=np.where(d['mask'],hh,0.)
        name=f'lateral_{px}um'
        variants.append((name,dict(cfg,candidate_id=name),d,hh,{},f'ASSUMED {px}um方格高度面积平均并保持入瞳'))
    dd=dict(d);dd['mask']=(d['coord'][:,None]**2+(d['coord'][None,:]-2)**2)<=cfg['R_um']**2
    variants.append(('aperture_decenter2um',dict(cfg,candidate_id='aperture_decenter2um'),dd,h,{},'ASSUMED 遮光孔径相对固定DOE偏心2um；高度不移动'))
    variants.append(('tilt01mrad',dict(cfg,candidate_id='tilt01mrad'),d,h,dict(tilt_mrad=.1),'ASSUMED 入射增加0.1mrad线性相位'))
    write(out/'fabrication_assumptions.json',dict(seed=cfg['seed'],cases=[dict(name=n,reason=reason,options=kw) for n,cc,dd,hh,kw,reason in variants],
         material_validation='NOT_TESTED',manufacturing_acceptance='NOT_TESTED',local_noise_rms_um=.020,local_noise_correlation_sigma_um=10.,
         minimum_linewidth_reason='当前采样不能认证亚微米特征；像素边缘跳变不是可微坡度'))
    fabrows=[]
    for name,cc,dd,hh,kwargs,reason in variants:
        z=dict(dd);z['height']=hh
        target=make_folder(out,name,cc,z,continuous=True)
        for w in STANDARD:acquire_case(out,target,z,hh,w,cc,**kwargs)
        rr,ll,ss,ii=evaluate(target,cc,STANDARD)
        fabrows.append(dict(condition=name,assumption=reason,**ss))
        del ii
    csvwrite(out/'gate3_fabrication.csv',fabrows)
    write(out/'gate3_fabrication.json',fabrows)
    # 像元积分只处理已有原始强度，记录相同能量与采样后形态，不再次传播。
    pixelrows=[]
    from optics import measure
    for pixel in [1,2,4,8]:
        raws=[]
        for w in STANDARD:
            raw,c,rec=load(base/'cases'/f'{w:g}nm.npz')
            n=raw.shape[0]//pixel
            a=raw.reshape(n,pixel,n,pixel).mean(axis=(1,3))
            cc=dict(cfg,pitch_um=float(pixel))
            coord=(np.arange(n)-(n-1)/2)*pixel
            r=measure(a,coord,rec,cc,w)
            pixelrows.append(dict(pixel_um=pixel,wavelength_nm=w,n01_status=r['n01_status'],n02_status=r['n02_status'],
               halfmax=r['halfmax_components'],outside_ratio=r['outside_main_disk_ratio'],
               energy_sum=float(a.sum()*pixel**2),angle_deg=r['raw_angle_deg'],reason='ASSUMED 方形100%填充像元积分，无实测MTF；冻结函数内部轴心门仍为1um历史假设'))
            raws.append(a.ravel())
        x=np.stack(raws,axis=1);x/=np.linalg.norm(x,axis=0)
        with (out/f'pixel_{pixel}um_gram.npz').open('xb') as f:np.savez_compressed(f,gram=x.T@x,wavelengths_nm=STANDARD)
    csvwrite(out/'gate3_pixel_integration.csv',pixelrows)
    # 采样可见结构复杂度与截面，不推断尚未给定的制造最小特征。
    gradx=np.diff(h,axis=1);grady=np.diff(h,axis=0)
    write(out/'fabrication_feature_statistics.json',dict(max_sampled_step_um=float(max(abs(gradx).max(),abs(grady).max())),
       fraction_horizontal_edges_gt_half_period=float(np.mean(abs(gradx)>.5*d['period_um'])),
       fraction_vertical_edges_gt_half_period=float(np.mean(abs(grady)>.5*d['period_um'])),
       grid_resolution_um=1.,certified_minimum_feature_um=None,maximum_physical_slope=None,
       reason='含包裹/量化台阶，离散高度差不等于侧壁坡度；需设备PSF、最小线宽、固化收缩、色散和侧壁表征'))
    textfile(out/'gate3_fabrication_tolerance.md',f"# G3 工艺/材料敏感性\n\nSIMULATED G3-Fabrication-Robustness: PASS（限已列假设扰动影响已定量，不代表所有扰动通过硬门）。\n实测加工验收：NOT_TESTED。共{len(fabrows)}组×25通道，连续/Q10-floor基线见B1/B2。各组形态/链接/能量/相关性见gate3_fabrication.csv及候选原始cases。\n材料Cauchy、常数及±0.005均为ASSUMED。局部噪声、圆角、横向采样、孔径偏心、倾斜参数见fabrication_assumptions.json，不能外推加工良率。像元积分见gate3_pixel_integration.csv。\n须确认：IP-Dip2实测色散、10级高度标定/误差分布、最小横向线宽/侧壁角、固化收缩、有效填充与传感器MTF。\n")
    write(out/'G3.json',dict(numerics=numerics,fabrication_quantification='PASS',fabrication_real_world='NOT_TESTED',
          exceptions=[dict(condition=r['condition'],n02_valid=r['n02_valid']) for r in fabrows if r['n02_valid']<25]))
    textfile(out/'completion_summary_batch2.md',f"# 批次2完成\n\n蓝端加密完成；G3-Numerics={numerics}；加工/材料假设扰动{len(fabrows)}组完成，实测工艺NOT_TESTED。能量分母为固定单位入瞳，不以ROI重归一替代收集效率。\n")
    # G2失败仍按任务书做有限几何诊断；数值失败时不扩展优化/双孔径。
    from selection import select
    select(out,cfg,numerics)


def plot_diffs(out,diffs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(diffs)//4,4,figsize=(15,3*(len(diffs)//4)),layout='constrained',squeeze=False)
    for ax,(name,w,diff) in zip(axes.ravel(),diffs):
        v=np.max(np.abs(diff));ax.imshow(diff,origin='lower',extent=[-256,256,-256,256],cmap='RdBu_r',vmin=-v,vmax=v)
        ax.set(xlim=(-100,100),ylim=(-100,100),title=f'{name} - B2 / {w:g}nm',xlabel='x (um)',ylabel='y (um)')
    fig.suptitle('Raw intensity differences (um^-2), local symmetric scales; ASM128 reference / experiments/n02/validation.py')
    fig.savefig(out/'gate3_convergence_differences.png',dpi=130);plt.close(fig)
