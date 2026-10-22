"""事后离线复核补充：澄清资源跳过、实际谱间隔及RS峰形；不覆盖v1。"""
import sys
sys.dont_write_bytecode=True
import argparse
from p0b_common import *
from p0b_locators import quadratic


def review(out):
    original_manifest=read(out/'manifest.json');resources=read(out/'resource_usage.json')
    rows=csvread(out/'diagnostics/blue_domains_trajectory.csv');corrected=[]
    for condition in sorted(set(r['condition'] for r in rows)):
        for locator in sorted(set(r['locator'] for r in rows)):
            rr=sorted([r for r in rows if r['condition']==condition and r['locator']==locator],key=lambda r:float(r['wavelength_nm']))
            for i,r in enumerate(rr):
                item=dict(r);w=float(r['wavelength_nm']);dw=w-float(rr[i-1]['wavelength_nm']) if i else None
                item['actual_delta_wavelength_nm']=dw
                item['scaled_min_angle_deg']=.4*dw if dw is not None else None
                item['scaled_max_angle_deg']=1.8*dw if dw is not None else None
                item['actual_spacing_scaled_gate']=(.4*dw<=float(r['delta_angle_deg'])<=1.8*dw) if dw is not None else None
                item['legacy_v1_gate_cell']=r['old_scaled_04_18_gate']
                item['revision_reason']='资源不足仅复用420/425/430nm pad4，5nm间隔须按实际谱间隔缩放；所有新口径仅诊断，无正式授予PASS'
                corrected.append(item)
    csvwrite(out/'diagnostics/blue_domains_trajectory_v2.csv',corrected)
    oldraw,c,rec=loadcase(OLD/'B2/cases/425nm.npz')
    pad4,c4,r4=loadcase(OLD/'convergence/cases/pad4_425nm.npz')
    fresnel,cf,rf=loadcase(out/'propagation/open_fresnel_425nm.npz')
    with np.load(out/'propagation/RS_points_425nm.npz',allow_pickle=False) as z:
        mask=z['point_kind']=='core_fine_quarter_um';xy=z['points_um'][mask];rs=z['intensity_raw'][mask].reshape(13,13)
    q=quadratic(rs,np.arange(13)*.25)
    rspos=dict(x_um=float(xy[0,0]+q['x_um']),y_um=float(xy[0,1]+q['y_um']),fit_valid=q['fit_valid'],
        grid_step_um=.25,grid_shape=[13,13],peak_intensity_raw=float(rs.max()),
        limitation='直接RS核但入瞳仍1um中点求积，不能替代像元内部求积收敛；3x3局部拟合仅诊断')
    write(out/'diagnostics/425_RS_subgrid_peak_v2.json',rspos)
    plot(out,oldraw,pad4,fresnel,rs,xy,rspos)
    ratios=csvread(out/'diagnostics/ratio_sensitivity_decomposition.csv')
    selected=[r for r in ratios if (float(r['wavelength_nm'])==546.1 and r['condition']=='dx05') or (float(r['wavelength_nm'])==660 and r['condition']=='pad4')]
    write(out/'review_corrections_v2.json',dict(time=now(),version='P0B-review-v2',post_hoc=True,
        base_manifest_sha256=sha(out/'manifest.json'),source_protocol_sha256=sha(out/'P0B_diagnostic_protocol.json'),
        old_gate_override=False,new_formal_gate=None,
        corrections=['当前资源RAM可用1.86GiB，低于2GiB下限；所有新增pad4/pad5均跳过。只复用4096/8192um旧域，没有10240um实算。',
        'pad4蓝端仅420/425/430nm，v1角差门单元未按实际5nm间隔缩放，v2独立表按实际delta_lambda修正。原两套1nm完整轨迹不受此项影响。',
        'GPU分配峰值0是没有新ASM调用的占位，不应表述成GPU资源占用为0。',
        '定位主审计8方向初值；扩域/开放参考的插值比较4方向初值，均为多初值诊断，不授予正式Gate。'],
        completed=dict(old_raw_npz=571,old_artifact_hashes=900,new_ASM=resources['new_ASM_calls'],
                       new_open_Fresnel=resources['new_Fresnel_calls'],new_local_RS=resources['new_RS_calls']),
        additional_quantitative_diagnostics=selected,rs425=rspos))
    decision=read(out/'P0B_gate_decision.json')
    decision.update(version='P0B-review-v2',time=now(),new_ASM_skipped_for_resource=True,
        prior_decision_preserved=True,resource_boundaries='没有新增pad4/pad5或完整全边界开放积分，不能假称大域已复核',
        next_minimal_experiment='只在420nm，对冻结1um B2高度的若干边界条带成对位置做2x2/4x4像元内RS求积，同点比较既有pad2/pad4：先区分真实衍射尾与周期/输入采样纹理。不改0.001门、不启动G4–G8。')
    write(out/'P0B_gate_decision_v2.json',decision)
    base=(out/'summary.md').read_text(encoding='utf-8')
    note=f'''# N02-1C-R 审核版 v2（本轮权威汇总）

本文件保留v1全部原始结果，增加离线核查澄清；没有覆盖v1、旧N02或Gate。最终P0B仍 **INCONCLUSIVE**；A支持 **EVALUATOR_INSTABILITY**，B仍 **INCONCLUSIVE**。G2/G3 FAIL不变。

## 必须优先阅读的更正与补充

- **实际资源范围**：新增大网格ASM为0。预检RAM仅{read(out/'resource_preflight.json')['memory']['ram_available_bytes']/2**30:.3f}GiB，低于2GiB下限；pad5预算还超过显存余量。只复用旧pad2/pad4与dx0.5数据；没有10240um新域计算。新增计算为13个非周期Fresnel积分及4组局部RS，CPU工作集峰值{resources['cpu_peak_working_set_bytes']/2**30:.3f}GiB。
- **谱间隔修正**：旧pad4蓝端只存在420/425/430nm。v1的三个点之间角差被误套1nm门，v2在`blue_domains_trajectory_v2.csv`按实际5nm间隔缩放。完整pad2与开放Fresnel的420–430nm/1nm结果保持；未据任何诊断表更改旧G2。
- **初值范围澄清**：A的六种估计器主审计使用8方向初值；B的插值比较使用4方向初值。`gpu_peak_allocated_bytes=0`只表示无新GPU ASM调用，不能解释为CUDA环境不占显存。
- **非边缘失败的机制证据**：546.1nm细采样原峰比差0.298764，在共同物理主盘中心下为0.002715；再统一像元面积采样为0.006625。660nm pad4原差0.103491，在共同中心下为0.009859。说明主盘中心及离散排除掩模有强敏感性；这些是并行诊断，**不放宽原0.1门**，也不证明原像元内部高度求积已收敛。
- **425nm开放RS峰形**：0.25um子网格的诊断峰坐标约({rspos['x_um']:.6f},{rspos['y_um']:.6f})um。核心49点中pad2/RS L1=0.002530524，pad4/RS L1=0.000007572。该局部证据支持微小数值扰动触发冻结拟合失稳；没有认证整ROI或全边界能量。

图：`diagnostics/425_open_reference_comparison_v2.png`；证据：`review_corrections_v2.json`、`P0B_gate_decision_v2.json`、`ratio_sensitivity_decomposition.csv`、`RS_core_error_summary.csv`。

## 下一项最小实验（替代v1的下一项建议）

{decision['next_minimal_experiment']}

## v1证据汇总（涉及计算域/初值/谱间隔的表述以上述v2澄清为准）

'''
    textfile(out/'summary_v2.md',note+base)
    reportdir=ROOT/'reports/n02_1c_r'/out.name
    textfile(reportdir/'summary_v2.md',note+base);write(reportdir/'P0B_gate_decision_v2.json',decision)
    names=['summary_v2.md','P0B_gate_decision_v2.json','review_corrections_v2.json',
           'diagnostics/blue_domains_trajectory_v2.csv','diagnostics/425_RS_subgrid_peak_v2.json','diagnostics/425_open_reference_comparison_v2.png']
    write(out/'review_manifest_v2.json',dict(time=now(),base_manifest_sha256=sha(out/'manifest.json'),
        revision_source=str(Path(__file__).relative_to(ROOT)),revision_source_sha256=sha(__file__),
        outputs={p:sha(out/p) for p in names},report_summary_sha256=sha(reportdir/'summary_v2.md')))
    print('离线审核v2完成，保留v1及旧G2/G3 FAIL',flush=True)


def plot(out,a,b,c,rs,xy,pos):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,4,figsize=(17,5),layout='constrained')
    for ax,img,title in zip(axes[:3],[a,b,c],['Frozen ASM pad2','Legacy ASM pad4','Open Fresnel CZT']):
        im=ax.imshow(img,origin='lower',extent=[-256,256,-256,256],cmap='inferno');ax.set(xlim=(8,20),ylim=(-27,-15),xlabel='x (um)',ylabel='y (um)',title=title);fig.colorbar(im,ax=ax,label='Intensity (um^-2)')
    x=xy[:,0].reshape(13,13)[0];y=xy[:,1].reshape(13,13)[:,0]
    im=axes[3].imshow(rs,origin='lower',extent=[x[0]-.125,x[-1]+.125,y[0]-.125,y[-1]+.125],cmap='inferno')
    axes[3].plot(pos['x_um'],pos['y_um'],'c+');axes[3].set(xlabel='x (um)',ylabel='y (um)',title='Direct RS / 0.25um output grid');fig.colorbar(im,ax=axes[3],label='Intensity (um^-2)')
    fig.suptitle('N02-1C-R / 425nm fixed B2 height / local scales and fields differ / p0b_review_v2.py')
    fig.savefig(out/'diagnostics/425_open_reference_comparison_v2.png',dpi=140);plt.close(fig)


def verify(out):
    m=read(out/'review_manifest_v2.json');assert sha(out/'manifest.json')==m['base_manifest_sha256']
    assert sha(ROOT/m['revision_source'])==m['revision_source_sha256']
    for p,h in m['outputs'].items():assert sha(out/p)==h
    rows=csvread(out/'diagnostics/blue_domains_trajectory_v2.csv')
    for r in rows:
        if r['actual_delta_wavelength_nm']:
            dw=float(r['actual_delta_wavelength_nm']);d=float(r['delta_angle_deg'])
            assert (r['actual_spacing_scaled_gate']=='True')==(.4*dw<=d<=1.8*dw)
    assert read(out/'P0B_gate_decision_v2.json')['status']=='INCONCLUSIVE'
    print(json.dumps(dict(review_v2='PASS',corrected_diagnostic_rows=len(rows),legacy_gates='FAIL_UNCHANGED'),ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);ap.add_argument('--verify',action='store_true');args=ap.parse_args()
    out=ROOT/'results/n02_1c_r'/args.run_id
    verify(out) if args.verify else review(out)
