"""只读来源审计、预检与先于计算冻结的点计划。"""
from r2_common import *


def prepare(out):
    (out/'figures').mkdir(exist_ok=False)
    write(out/'preservation_before.json',snapshot());textfile(out/'git_dirty_before.txt',git('status','--short'))
    inputs=[TASK,OLD/'B2/height_um.npy',OLD/'B2/aperture_mask.npy',OLD/'B2/config.json',OLD/'B2/frozen_sha256.json',
       OLD/'protocol_frozen.json',OLD/'gates.json',OLD/'gate3_convergence.csv',OLD/'gate3_convergence.json',
       UP/'P0B_diagnostic_protocol.json',UP/'review_corrections_v2.json',UP/'P0B_gate_decision_v2.json',UP/'review_manifest_v2.json',
       UP/'diagnostics/ratio_sensitivity_decomposition.csv',UP/'diagnostics/RS_core_error_summary.csv',UP/'diagnostics/425_fit_audit.csv',
       UP/'diagnostics/blue_domains_trajectory_v2.csv',UP/'propagation/RS_points_425nm.npz',UP/'diagnostics/RS_point_comparison.csv',
       ROOT/'reports/n02_1c_r/n02_1cr_20261020_01/summary_v2.md',ROOT/'reports/n02/n02_20261019_02/N02_final_decision.md']
    inputs+=list((ROOT/'experiments/n02').glob('*.py'))+list((ROOT/'experiments/n02_1c_r').glob('*.py'))
    inputs+=[ROOT/'experiments/N01_1/model.py',ROOT/'experiments/N01_2A/model.py',ROOT/'src/spiral_hsi/optics/propagation.py']
    for w in [420,425,546.1,660]:
        inputs.append(OLD/'B2/cases'/f'{w:g}nm.npz')
        inputs.append(OLD/'convergence/cases'/f'pad4_{w:g}nm.npz')
    inputs.append(OLD/'convergence/cases/dx05_546.1nm.npz')
    hashes={p.as_posix():sha(p) for p in inputs};write(out/'input_hashes.json',hashes)
    frozen=read(OLD/'B2/frozen_sha256.json');assert sha(OLD/'B2/height_um.npy')==frozen['height_um.npy']
    assert sha(OLD/'B2/aperture_mask.npy')==frozen['aperture_mask.npy']
    prior=read(UP/'review_manifest_v2.json')
    for p,digest in prior['outputs'].items():assert sha(UP/p)==digest
    assert sha(UP/'manifest.json')==prior['base_manifest_sha256']
    oldg=read(OLD/'gates.json');assert oldg['G2']['status']==oldg['G3_Numerics']['status']=='FAIL'
    assert read(UP/'P0B_gate_decision_v2.json')['status']=='INCONCLUSIVE'
    cfg,h,mask,src=source_pixels()
    assert cfg['R_um']==500 and cfg['focal_mm']==20 and cfg['object_mm']==180 and cfg['sensor_mm']==22.495
    assert cfg['design_nm']==546.1 and cfg['Q']==10 and cfg['pitch_um']==1 and cfg['n_env']==1
    write(out/'config_resolved.json',cfg)
    write(out/'input_audit.json',dict(status='PASS',absolute_old_run=OLD,absolute_upstream_run=UP,
       height_file_sha256=sha(OLD/'B2/height_um.npy'),height_array_sha256=ahash(h),height_unit='um',
       height_max_um=float(h.max()),mask_sha256=sha(OLD/'B2/aperture_mask.npy'),source_pixels=len(src['x']),
       area_per_source_pixel_um2=1.,normalization_K=src['K'],incident_unscaled_midpoint_power_um2=src['incident_midpoint_power'],
       old_gates=oldg,prior_P0B='INCONCLUSIVE',
       coordinates='(index-(N-1)/2)*dx，x向右y向上；输出半像元格；正向exp(+ikR)',
       pupil_interpretation='原高度与二值孔径像元分片常值；半径500um在旧mask像元化，不另行改变孔径边缘'))
    env=dict(time=now(),python=sys.executable,python_version=sys.version,numpy=np.__version__,scipy=scipy.__version__,
        torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),platform=platform.platform(),
        git_head=git('rev-parse','HEAD').strip(),seed=20261020)
    write(out/'environment.json',env);textfile(out/'task_original.md',TASK.read_text(encoding='utf-8'))
    mem=memory();plans=[]
    for pad in [2,4]:
        n=2048*pad;need=3*16*n*n+512*2**20
        allowed=need<.75*mem['gpu_free_bytes'] and mem['ram_available_bytes']>.75*2**30
        plans.append(dict(pad=pad,N=n,physical_width_um=n,estimated_gpu_bytes=need,
             allowed=allowed,status='PLANNED_SELECTED_POINT_ASM' if allowed else 'NOT_RUN_RESOURCE_LIMIT'))
    device='cuda' if mem['gpu_free_bytes']>1024*2**20 else 'cpu'
    rs_allowed=mem['ram_available_bytes']>512*2**20
    resource=dict(time=now(),memory=mem,disk_free_bytes=shutil.disk_usage(ROOT).free,RS_device=device,RS_allowed=rs_allowed,
         selected_point_ASM=plans,no_full_pad5_pad8=True,RS_temporary_cap_MiB=384,
         distinction='选点ASM仍需pad2/pad4二维GPU FFT谱，但不分配完整相位核/传播复场/整域强度；主机只保留小块与少量输出')
    write(out/'resource_preflight.json',resource)
    protocol=read(ROOT/'configs/n02_1c_r2/protocol_v1.json');write(out/'protocol_locked.json',protocol)
    plan=boundary_plan(out);peak=peak_plan(out,cfg)
    source_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in CODE.glob('*.py')}
    source_hashes['configs/n02_1c_r2/protocol_v1.json']=sha(ROOT/'configs/n02_1c_r2/protocol_v1.json')
    write(out/'source_hashes.json',source_hashes)
    write(out/'preregistration.json',dict(time=now(),protocol_sha256=sha(out/'protocol_locked.json'),
       boundary_plan_sha256=sha(out/'boundary_sample_plan.json'),peak_plan_sha256=sha(out/'peak_sample_plan.json'),
       input_hashes_sha256=sha(out/'input_hashes.json'),source_hashes_sha256=sha(out/'source_hashes.json')))
    return cfg,h,mask,src,env,resource,plan,peak


def boundary_plan(out):
    pts={}
    def add(x,y,group,detail,q8=False):
        key=(x,y)
        if key not in pts:pts[key]=dict(x_um=x,y_um=y,group=group,detail=detail,q8_preregistered=q8)
    for x in [-.5,.5]:
        for y in [-.5,.5]:add(x,y,'center_control','光轴附近四个实际半像元中心')
    _,_,r=loadcase(OLD/'B2/cases/420nm.npz')
    add(r['argmax_x_um'],r['argmax_y_um'],'peak_control','冻结420nm最亮格点')
    add(-r['argmax_x_um'],-r['argmax_y_um'],'opposite_peak_control','几何中心反向，不假设强度相等')
    for depth in [0,8,16,32,64]:
        v=2047.5-depth
        for x,y in [(v,.5),(-v,-.5),(.5,v),(-.5,-v)]:
            add(x,y,'edge_normal',f'从外侧像元中心向内{depth}um；距物理域边界{depth+.5}um',depth in [0,8])
    for tangent in [-1024.5,1024.5]:
        v=2039.5
        for x,y in [(v,tangent),(-v,-tangent),(tangent,v),(-tangent,-v)]:add(x,y,'edge_tangent','16um条带内，沿边对称位置')
    for sx in [-1,1]:
        for sy in [-1,1]:add(sx*2039.5,sy*2039.5,'corner','近角点，几何对称，不重复计边')
    for x,y in [(2055.5,.5),(-2055.5,-.5),(.5,2055.5),(-.5,-2055.5)]:add(x,y,'outside_pair','超出pad2域，pad2仅按周期延拓求值')
    rows=list(pts.values())
    for i,r in enumerate(rows):
        r['point_id']=f'B{i:03d}';r['opposite_id']=next((f'B{j:03d}' for j,s in enumerate(rows) if s['x_um']==-r['x_um'] and s['y_um']==-r['y_um']),None)
        r['inside_pad2']=abs(r['x_um'])<2048 and abs(r['y_um'])<2048
        r['in_16um_boundary_strip']=r['inside_pad2'] and max(abs(r['x_um']),abs(r['y_um']))>=2032
        r['source_label']='frozen_original / parallel_diagnostic / physical_reference并排'
    write(out/'boundary_sample_plan.json',dict(wavelength_nm=420,points=rows,selection='先于求值冻结；不是看PSF/残差后筛点',
         symmetry='几何中心反向点(x,y)和(-x,-y)；实际螺旋PSF不应预设中心对称',
         sparse_limit='不对这些点作面积加权或据此估算整条带edge_fraction'))
    return rows


def peak_plan(out,cfg):
    v=next(r for r in csvread(UP/'diagnostics/ratio_sensitivity_decomposition.csv') if float(r['wavelength_nm'])==546.1 and r['condition']=='dx05')
    common=[float(v['common_center_x_um']),float(v['common_center_y_um'])]
    radius=1.22*.5461*cfg['sensor_mm']*1000/(2*cfg['R_um'])
    conditions=[('pad2',OLD/'B2/cases/546.1nm.npz'),('pad4',OLD/'convergence/cases/pad4_546.1nm.npz'),('dx05',OLD/'convergence/cases/dx05_546.1nm.npz')]
    positions={};defs=[]
    def add(x,y,role):
        k=(float(x),float(y));positions.setdefault(k,dict(x_um=k[0],y_um=k[1],roles=[]))['roles'].append(role)
    for tag,path in conditions:
        raw,c,rec=loadcase(path);yy,xx=np.meshgrid(c,c,indexing='ij');main=np.unravel_index(raw.argmax(),raw.shape)
        add(c[main[1]],c[main[0]],tag+'_main')
        for mode,center in [('a_frozen_own',[rec['peak_x_um'],rec['peak_y_um']]),('b_common',common)]:
            outside=(xx-center[0])**2+(yy-center[1])**2>radius**2
            ind=np.unravel_index(np.where(outside,raw,-1).argmax(),raw.shape)
            add(c[ind[1]],c[ind[0]],tag+'_'+mode+'_side')
            defs.append(dict(condition=tag,mode=mode,center_um=center,main_xy_um=[float(c[main[1]]),float(c[main[0]])],
                side_xy_um=[float(c[ind[1]]),float(c[ind[0]])],main_intensity=float(raw.max()),side_intensity=float(raw[ind]),
                outside_ratio=float(raw.max()/raw[ind]),source_file_sha256=sha(path)))
    # 统一原生1um的候选像元，供输出面积积分；取预置候选就近原网格中心，不扩成整图。
    native=set()
    for p in positions:
        native.add((float(np.rint(p[0]-.5)+.5),float(np.rint(p[1]-.5)+.5)))
    rows=list(positions.values())
    for i,r in enumerate(rows):r['point_id']=f'P{i:03d}'
    plan=dict(wavelength_nm=546.1,common_center_um=common,disk_radius_um=radius,points=rows,
        output_area_cells_um=[list(p) for p in sorted(native)],frozen_definitions=defs,input_q=[1,2,4],output_quadrature=2,
        warning='新RS仅在预注册主/旁峰候选坐标求值；得到局部候选比，不能认证整ROI全局主盘外最大值。旧dx05同时重新采样高度，本轮新RS始终只用原分片常值高度。')
    write(out/'peak_sample_plan.json',plan)
    write(out/'peak_ratio_definitions.json',dict(original_numerator='512um ROI全部像素最大强度；无连续插值，无主盘能量',
        original_denominator='所有距各自拟合中心严格大于1.22lambda*z/D的ROI像素中最大强度；不要求是独立局部旁峰',
        distinct_side_ratio='另行用3x3局部极大且在主盘外的候选定义，不能与outside_main_disk_ratio混用',
        common_center=common,physical_radius_um=radius,source_code_paths=['experiments/N01_1/model.py:analyze','experiments/N01_2A/model.py:measure'],
        modes=dict(a='旧冻结各自中心及离散掩模，仅回读不替换',b='同一共同中心、各自原生采样',
          c='同一1um候选像元内2x2输出面积求积；同时列中心判外与物理半径裁切的面积均值；仍是局部候选集合'),
        threshold_0_1='原两条件outside_ratio绝对差上限不变，不是峰比阈值；新局部比不授予Gate'))
    return plan
