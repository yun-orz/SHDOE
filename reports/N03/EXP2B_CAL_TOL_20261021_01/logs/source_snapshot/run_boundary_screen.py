"""B：只对原420nm八个输出边界点做一次q8/q16源像元求积。"""
import argparse
import ctypes
import importlib.util
import traceback
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    out=new_output(parser.parse_args().output);started=time.perf_counter();before=gitstate()
    try:
        optics=ROOT/'optics/n02_single_spiral';old=optics/'results/n02/n02_20261019_02';b2=old/'B2'
        r2=optics/'results/n02_1c_r2/n02_1cr2_20261020_02'
        protocol_path=optics/'configs/n02_1c_r2/protocol_v1.json'
        protocol=read(protocol_path);plan=read(r2/'boundary_sample_plan.json');pre=read(r2/'preregistration.json')
        if sha(r2/'boundary_sample_plan.json')!=pre['boundary_plan_sha256']:raise RuntimeError('原预注册点计划哈希不一致')
        for p,h in read(r2/'artifact_manifest.json').items():
            if sha(r2/p)!=h:raise RuntimeError(f'原R2产物哈希不一致：{p}')
        fixed=[p for p in plan['points'] if p['q8_preregistered']]
        points=np.array([[p['x_um'],p['y_um']] for p in fixed])
        with np.load(r2/'raw/P1_RS_q8.npz',allow_pickle=False) as z:
            old_points=z['points_um'].copy();old_ids=z['point_id'].copy();old_field=z['field_without_global_piston'].copy()
            old_meta=json.loads(z['meta_json'].item())
        frozen=read(b2/'frozen_sha256.json')
        for name in ['height_um.npy','aperture_mask.npy','config.json']:
            if sha(b2/name)!=frozen[name]:raise RuntimeError('固定B2资产哈希失败：'+name)
        report_path=optics/'reports/n02_1c_r2/n02_1cr2_20261020_02/N02_1CR2_final_audit.md'
        report_path.read_text(encoding='utf-8');read(old/'gates.json');formal_protocol=read(old/'protocol_frozen.json')
        solver_path=optics/'experiments/n02_1c_r2/r2_solver.py';common_path=optics/'experiments/n02_1c_r2/r2_common.py'
        memory_path=optics/'experiments/n02_1c_r/p0b_common.py'
        env=dict(np=np,torch=torch,time=time,ctypes=ctypes,read=read,OLD=old)
        memory,mem_interface=extract_function(memory_path,'memory',env)
        source_pixels,source_interface=extract_function(common_path,'source_pixels',env)
        rs,rs_interface=extract_function(solver_path,'rs',env)
        cfg,height,mask,source=source_pixels()
        paths=[p for p in r2.rglob('*') if p.is_file()]+[b2/'height_um.npy',b2/'aperture_mask.npy',b2/'config.json',b2/'frozen_sha256.json',
                 b2/'cases/420nm.npz',old/'gates.json',old/'protocol_frozen.json',old/'gate3_convergence.csv',protocol_path,
                 report_path,solver_path,common_path,memory_path,optics/'experiments/n02_1c_r2/r2_analysis.py',optics/'experiments/n02_1c_r2/r2_prepare.py',
                 optics/'experiments/n02_1c_r2/r2_experiments.py',optics/'experiments/n02/validation.py',
                 optics/'vendor_compat/experiments/N01_1/model.py',ROOT/'README.md']
        inputs=freeze(out,paths)
        current=memory();gpu=bool(torch.cuda.is_available())
        estimated_gpu=int(old_meta['gpu_peak_allocated_bytes']*4*1.5+128*2**20)
        estimated_seconds=float(old_meta['seconds']*5*4+20)
        allowed=gpu and estimated_gpu<current['gpu_free_bytes']*.75 and estimated_seconds<1800
        config=dict(notice=NOTICE,branch='B_FIXED_BOUNDARY_SCREEN',environment=environment('CUDA' if gpu else 'NONE'),git_before=before,task_source=task_source(),
                    wavelength_nm=420,points=fixed,quantity='RS1 complex field and point intensity at 8 output-plane positions, not 2D PSF or source points',
                    quadrature=[8,16],pixel_chunk=8192,point_chunk=4,physics=cfg,
                    normalization=dict(K=source['K'],source_pixels=len(source['x']),source_cell_area_um2=1,
                                       definition='original 1um midpoint incident normalization; same K both q; no per-q or ROI renormalization'),
                    thresholds=dict(raw_intensity_vector_L1=0.01,relative_complex_field_per_point=protocol['diagnostic_convergence']['relative_complex_field_limit'],
                                    relative_intensity_per_point=protocol['diagnostic_convergence']['relative_intensity_limit'],
                                    formal_edge_fraction_limit_UNCHANGED=formal_protocol['convergence']['edge_fraction_max'],
                                    old_425_fit_max_offset_pixel_UNCHANGED=1),
                    criterion='new raw vector L1<=1% AND preserved R2 per-point complex<=1% and intensity<=2%; local diagnostic only, not G2/G3',
                    L1_definition='sum_i |I8_i-I16_i| / sum_i |I16_i|; same fixed K, no normalizing the two vectors separately',
                    field_definition='global exp(ikz) removed identically, phase and normalization match frozen R2',
                    geometry='original 2048² source cells at pitch1um; fixed mask, piecewise constant height and aperture per original pixel; source subcells do not reclip circular pupil; output points on original pad2=4096um boundary',
                    historical_q8_meta=old_meta,interfaces=dict(rs=rs_interface,source_pixels=source_interface,memory=mem_interface),
                    resource=dict(before=current,estimated_peak_GPU_bytes=estimated_gpu,estimated_pair_seconds=estimated_seconds,allowed=allowed,
                                  method='historical q8 peak x4 x1.5 +128MiB; pair time historical q8 x5 x4 +20s',
                                  historical_cap_note='R2 384MiB temporary estimate applied to q<=8; new q16 expected larger at same chunks, explicitly checked against free VRAM'),
                    original_gates=dict(N02_G2='FAIL_UNCHANGED',N02_G3_Numerics='FAIL_UNCHANGED',N03_G0='FAIL_UNCHANGED'),
                    NOT_RERUN=['420nm full-domain edge','660nm full-domain edge','425nm localization','blue wavelength angle gates','ASM or FFT propagation'])
        write(out/'run_config.json',config);csvwrite(out/'fixed_points.csv',fixed)
        preflight=(f'# B运行前审计\n\n{NOTICE}\n\n原boundary_sample_plan哈希与preregistration一致，原R2产物哈希逐项通过；固定8点为'+', '.join(p['point_id'] for p in fixed)+
                   '。它们是像面边界输出位置，不是源面采样点；仅得到8个复场/强度值，不构造二维PSF或ROI边缘能量。\n\n'+
                   f'只读提取原r2_solver.py:{rs_interface["line"]}的rs函数和r2_common.py:{source_interface["line"]}的source_pixels函数，不改函数体，不运行旧入口。'+
                   '同K、同几何、同8192源像元/4输出点块，仅q从8变16；高度/孔径在原像元内分片常值。\n\n'+
                   f'历史q8={old_meta["seconds"]:.3f}s，估计成对筛查{estimated_seconds:.1f}s，估计GPU峰值{estimated_gpu/2**30:.3f}GiB，当前空闲{current["gpu_free_bytes"]/2**30:.3f}GiB，allowed={allowed}。'+
                   '阈值已冻结：同通量强度向量L1≤1%，并保留R2每点复场≤1%/强度≤2%诊断口径；不替代原edge<0.001或425nm拟合偏移≤1pixel门。\n')
        textfile(out/'00_preflight.md',preflight)
        event(out,started,'CONTRACT_FROZEN',points=8,estimated_gpu_bytes=estimated_gpu,estimated_pair_seconds=estimated_seconds,allowed=allowed)
        if not allowed:
            textfile(out/'screen_result.md','# B BLOCKED\n\n'+NOTICE+'\n\n资源预估未满足本任务安全预算；未运行8/16成对计算。详情见00_preflight/run_config。等待审核，不改点、不降精度、不扩大任务。\n')
            write(out/'qa.json',dict(status='BLOCKED',reason='RESOURCE_PREFLIGHT',pair_calls=0))
            textfile(out/'DELIVERY.md','# B正式入口\n\nBLOCKED，见screen_result.md和00_preflight.md；原门不变。\n')
            finish(out,started,'BLOCKED',before,inputs,device='CUDA' if gpu else 'NONE',pair_calls=0);return
        testpath=CODE.parent/'tests/test_n03_exp2b.py';sp=importlib.util.spec_from_file_location('exp2b_b_tests',testpath);test=importlib.util.module_from_spec(sp);sp.loader.exec_module(test)
        checks=test.b_checks(fixed,old_points,old_ids,source,cfg)
        if any(not r['passed'] for r in checks):write(out/'tests.json',checks);raise RuntimeError('B固定点/几何检查失败')
        results={};metas={}
        (out/'raw').mkdir()
        # 原8点q8和q16各调用一次，不按结果挑点、不改变q、不额外重试。
        for q in [8,16]:
            event(out,started,'RS_START',q=q,points=8)
            value,meta=rs(source,points,420,cfg,q,device='cuda',pixel_chunk=8192,point_chunk=4)
            if not np.isfinite(value).all():raise RuntimeError('非有限RS结果')
            results[q]=value;metas[q]=meta
            with (out/f'raw/RS_q{q}.npz').open('xb') as f:
                np.savez_compressed(f,points_um=points,point_id=old_ids,field_without_global_piston=value,intensity_raw=abs(value)**2,meta_json=json.dumps(meta,ensure_ascii=False))
            event(out,started,'RS_COMPLETE',q=q,seconds_level=meta['seconds'],incident_energy=meta['incident_quadrature_energy'],GPU_peak_bytes=meta['gpu_peak_allocated_bytes'])
        reference_error=float(np.max(abs(results[8]-old_field)/np.maximum(abs(old_field),1e-12)))
        checks.append(dict(name='新q8与原q8复场回归',passed=reference_error<1e-10,value=reference_error))
        if reference_error>=1e-10:write(out/'tests.json',checks);raise RuntimeError('q8未复现原始积分路径；停止解释q16')
        u8,u16=results[8],results[16];i8,i16=abs(u8)**2,abs(u16)**2
        vector_l1=float(np.sum(abs(i8-i16))/np.sum(i16))
        shape_l1=float(np.sum(abs(i8/i8.sum()-i16/i16.sum())))
        compare=[]
        for p,a,b,ia,ib in zip(fixed,u8,u16,i8,i16):
            field_error=float(abs(a-b)/max(abs(b),1e-12));intensity_error=float(abs(ia-ib)/max(ib,1e-24))
            compare.append(dict(point_id=p['point_id'],x_um=p['x_um'],y_um=p['y_um'],U8_real=float(a.real),U8_imag=float(a.imag),U16_real=float(b.real),U16_imag=float(b.imag),
                                intensity8=float(ia),intensity16=float(ib),absolute_intensity_difference=float(abs(ia-ib)),relative_intensity_difference=intensity_error,
                                relative_complex_difference=field_error,phase_difference_rad=float(np.angle(b*np.conj(a))),
                                local_R2_field_limit_pass=field_error<=config['thresholds']['relative_complex_field_per_point'],
                                local_R2_intensity_limit_pass=intensity_error<=config['thresholds']['relative_intensity_per_point'],
                                intensity_unit='um^-2 per original unit midpoint incident power',quantity='single output-point intensity; no pixel area integration'))
        screen_pass=vector_l1<=.01 and all(r['local_R2_field_limit_pass'] and r['local_R2_intensity_limit_pass'] for r in compare)
        status='B_SCREEN_PASS_LOCAL_ONLY' if screen_pass else 'B_SCREEN_FAIL'
        csvwrite(out/'quadrature_compare.csv',compare);write(out/'tests.json',checks)
        qa=dict(status=status,new_vector_L1=vector_l1,secondary_separately_normalized_vector_L1=shape_l1,
                max_absolute_intensity_difference=float(np.max(abs(i8-i16))),max_abs_difference_over_I16_peak=float(np.max(abs(i8-i16))/max(i16)),
                max_relative_point_intensity_difference=max(r['relative_intensity_difference'] for r in compare),
                max_relative_point_complex_difference=max(r['relative_complex_difference'] for r in compare),q8_history_relative_field_error=reference_error,
                kernel_calls=dict(q8=1,q16=1),normalization='same fixed K; no ROI/vector renormalization in primary L1',
                original_gates=config['original_gates'],not_rerun=config['NOT_RERUN'])
        write(out/'qa.json',qa)
        fig,axes=plt.subplots(1,2,figsize=(11,4.8));x=np.arange(8)
        axes[0].semilogy(x,i8,'o-',label='q8');axes[0].semilogy(x,i16,'s--',label='q16');axes[0].set(ylabel='Raw point intensity (um^-2)',xlabel='Frozen output point')
        axes[1].plot(x,[r['relative_intensity_difference'] for r in compare],'o-',label='point intensity relative change');axes[1].plot(x,[r['relative_complex_difference'] for r in compare],'s-',label='complex field relative change')
        axes[1].axhline(.01,color='k',ls=':',label='1% diagnostic scale');axes[1].set(ylabel='Relative change',xlabel='Frozen output point')
        for ax in axes:ax.set_xticks(x,list(old_ids),rotation=45);ax.grid(alpha=.2);ax.legend(fontsize=7)
        fig.suptitle(f'420nm / 8 frozen boundary output points; q8 vs q16; vector L1={vector_l1:.5g}\n{status}; no full ROI or edge_fraction calculation',fontsize=10)
        fig.text(.5,.015,NOTICE,ha='center',fontsize=7);fig.tight_layout(rect=(0,.07,1,.88));fig.savefig(out/'figures/quadrature_comparison.png',dpi=150);plt.close(fig)
        report=['# B：固定几何局部求积筛查','',NOTICE,'',f'**{status}**','',
                f'同K的8点原始强度向量L1 = {vector_l1:.9g}（阈值≤0.01）。最大单点复场相对变化={qa["max_relative_point_complex_difference"]:.9g}，最大单点强度相对变化={qa["max_relative_point_intensity_difference"]:.9g}。',
                f'最大绝对强度差={qa["max_absolute_intensity_difference"]:.9g}um^-2，相对q16点集峰值差={qa["max_abs_difference_over_I16_peak"]:.9g}。辅助单独归一向量形状L1={shape_l1:.9g}，不作为主筛查以免掩盖幅值差。',
                f'新q8与冻结q8最大逐点复场相对差={reference_error:.9g}。固定K={source["K"]:.16g}；q8/q16入瞳求积功率分别为{metas[8]["incident_quadrature_energy"]:.15g}/{metas[16]["incident_quadrature_energy"]:.15g}，没有逐级强制归一。',
                f'本轮q8/q16各调用一次，耗时{metas[8]["seconds"]:.4g}/{metas[16]["seconds"]:.4g}s，GPU峰值{max(m["gpu_peak_allocated_bytes"] for m in metas.values())/2**30:.4g}GiB；float64/complex128、CUDA。',
                '这是原1um分片常值高度/孔径下源像元8×8→16×16中点求积，输出仅8个固定边界位置的复场和强度。高度、mask、原光轴、口径、传播距离、源网格、点位及K不变，未进行新ASM/FFT传播。复用原rs函数的重新计算不是独立光学实验。',
                '原R2逐点复场≤1%与强度≤2%尺度保留，本轮新增强度向量L1≤1%只是探索筛查。每点身份、坐标、复场实虚部、相位差及阈值见fixed_points.csv和quadrature_compare.csv。','',
                '|点|x um|y um|相对复场差|相对强度差|','|---|---:|---:|---:|---:|']
        for r in compare:report.append(f'|{r["point_id"]}|{r["x_um"]}|{r["y_um"]}|{r["relative_complex_difference"]:.6g}|{r["relative_intensity_difference"]:.6g}|')
        report+=['','**没有二维PSF、ROI能量或全边缘份额结果。** 不给单点标量套用PSF L1，不给8点强度之和乘面积冒充ROI积分。420/660nm全域边缘、425nm定位、蓝端角度门全部NOT_RERUN；仅引用原失败状态。原edge<0.001、425nm拟合最大偏移≤1pixel以及全部G2/G3要求未放宽。',
                 '局部通过仅说明这8个高风险位置在两个求积等级间达到预注册一致性，不等于16阶对连续极限已严格收敛，不等于全域/全波段认证。若失败亦直接停止，不循环换点/ROI/求积。',
                 '下一步仅候选：审核后针对原G2/G3全门开展一次资源受控的完整复核方案；本轮不执行。A位置容差独立验收，本结论不能与A合并为DOE验证PASS。']
        textfile(out/'screen_result.md','\n'.join(report)+'\n')
        textfile(out/'DELIVERY.md','# B正式入口\n\n'+NOTICE+'\n\n'+status+'，只读[screen_result.md](screen_result.md)、[qa.json](qa.json)和[quadrature_compare.csv](quadrature_compare.csv)。未重新执行全域边缘或蓝端门，原G0/G2/G3不变。\n')
        finish(out,started,status,before,inputs,device='CUDA',pair_calls=2,tests=len(checks),screen_vector_L1=vector_l1)
    except Exception:
        textfile(out/'logs/failure.txt',traceback.format_exc());event(out,started,'FAILED_STOP',error=traceback.format_exc().splitlines()[-1]);raise


if __name__=='__main__':main()
