"""多峰候选图：保留所有可行连接，不强制一对一，不冒充物理身份。"""
import sys
sys.dont_write_bytecode = True
import json
import math
from pathlib import Path
import numpy as np
from scipy.ndimage import maximum_filter
from runtime import ROOT, EXP, load, write_json, write_csv, old, legacy


def angle_delta(a, b):
    return (b-a+180)%360-180


def refine(raw, rr, cc, coord):
    """3×3对数二次极大拟合；失败保留像素中心，不强制成功。"""
    offset = np.zeros(2)
    fitted = False
    if 0 < rr < raw.shape[0]-1 and 0 < cc < raw.shape[1]-1:
        yy, xx = np.mgrid[-1:2, -1:2]
        mat = np.column_stack([np.ones(9), xx.ravel(), yy.ravel(), xx.ravel()**2, (xx*yy).ravel(), yy.ravel()**2])
        b = np.linalg.lstsq(mat, np.log(np.maximum(raw[rr-1:rr+2, cc-1:cc+2], np.finfo(float).tiny)).ravel(), rcond=None)[0]
        h = np.array([[2*b[3], b[4]], [b[4], 2*b[5]]])
        if np.linalg.eigvalsh(h).max() < 0:
            delta = -np.linalg.solve(h, b[1:3])
            if np.max(np.abs(delta)) <= 1:
                offset = delta
                fitted = True
    return float(coord[cc]+offset[0]), float(coord[rr]+offset[1]), fitted


def extract(raw, coord, record, cfg, settings, wave):
    params = settings['peak_analysis']
    maxima = (raw == maximum_filter(raw, size=3, mode='constant')) & (raw >= raw.max()*params['relative_intensity_floor'])
    positions = np.argwhere(maxima)
    candidates = sorted(positions.tolist(), key=lambda p: (-raw[p[0],p[1]], p[0], p[1]))
    sep = 1.22*(wave/1000)*cfg['sensor_mm']*1000/cfg['diameter_um']
    selected = []
    for rr, cc in candidates:
        if all(math.hypot(rr-r, cc-c) >= sep for r,c in selected):
            selected.append((rr,cc))
        if len(selected) == params['max_peaks']: break
    rows = []
    second = float(raw[selected[1]]) if len(selected) > 1 else 0.
    for rank,(rr,cc) in enumerate(selected,1):
        x,y,fitted = refine(raw, rr, cc, coord)
        theta = math.degrees(math.atan2(y,x))
        pixel_angle = math.degrees(math.atan2(coord[rr],coord[cc]))
        rows.append(dict(wavelength_nm=wave, peak_id=f'{wave}_p{rank}', rank=rank, pixel_row=rr, pixel_col=cc,
                         x_um=x, y_um=y, r_um=math.hypot(x,y), angle_deg=theta, raw_peak=float(raw[rr,cc]),
                         relative_to_brightest=float(raw[rr,cc]/raw.max()), fit_pass=fitted,
                         angle_pixel_fit_offset_deg=abs(angle_delta(pixel_angle,theta)),
                         peak_to_next_competitor_gap_raw=float(raw.max()-second),
                         strongest_competitor_relative_height=second/float(raw.max()),
                         halfmax_components=record['halfmax_components'], original_status=record['status'],
                         original_failure_reason=record['invalid_reason'], roi_capture_fraction=record['crop_fraction'],
                         strongest_peak_minus_this_peak_raw=float(raw.max()-raw[rr,cc]),
                         selection_min_separation_um=sep))
    return rows


def patch_cosine(rawa, a, rawb, b, half):
    def patch(raw,p):
        r,c = p['pixel_row'],p['pixel_col']
        if min(r,c) < half or max(r,c) >= raw.shape[0]-half: return None
        return raw[r-half:r+half+1,c-half:c+half+1].ravel()
    x,y = patch(rawa,a),patch(rawb,b)
    if x is None or y is None: return None
    return float(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)))


def edges_for(w1,w2, peaks, images, params):
    edges = []
    for a in peaks[w1]:
        for b in peaks[w2]:
            distance = math.hypot(a['x_um']-b['x_um'], a['y_um']-b['y_um'])
            radial = b['r_um']-a['r_um']
            angle = angle_delta(a['angle_deg'], b['angle_deg'])
            intensity_factor = max(a['raw_peak']/b['raw_peak'], b['raw_peak']/a['raw_peak'])
            cosine = patch_cosine(images[w1],a,images[w2],b,params['patch_halfwidth_pixels'])
            if distance > params['match_max_distance_um'] or abs(radial) > params['match_max_radial_change_um'] or abs(angle) > params['match_max_angle_change_deg'] or intensity_factor > params['match_max_intensity_factor'] or cosine is None or cosine < params['match_min_patch_cosine']:
                continue
            cost = .45*distance/params['match_max_distance_um']+.1*abs(radial)/params['match_max_radial_change_um']+.05*abs(angle)/params['match_max_angle_change_deg']+.15*math.log(intensity_factor)/math.log(params['match_max_intensity_factor'])+.25*(1-cosine)
            edges.append(dict(wavelength_from_nm=w1, wavelength_to_nm=w2, from_peak_id=a['peak_id'], to_peak_id=b['peak_id'],
                              from_rank=a['rank'], to_rank=b['rank'], spatial_distance_um=distance, radial_delta_um=radial,
                              angle_delta_deg=angle, intensity_factor=intensity_factor, patch_cosine=cosine, cost=cost,
                              from_is_brightest=a['rank']==1, to_is_brightest=b['rank']==1))
    for e in edges:
        outgoing = sum(x['from_peak_id']==e['from_peak_id'] for x in edges)
        incoming = sum(x['to_peak_id']==e['to_peak_id'] for x in edges)
        e.update(outgoing_choices=outgoing, incoming_choices=incoming,
                 matching_status='UNIQUE_WITHIN_GATES' if outgoing==incoming==1 else 'AMBIGUOUS_MULTIPLE',
                 physical_identity_confirmed=False)
    for side,w,key in [('from',w1,'from_peak_id'),('to',w2,'to_peak_id')]:
        for p in peaks[w]:
            if not any(e[key]==p['peak_id'] for e in edges):
                edges.append(dict(wavelength_from_nm=w1,wavelength_to_nm=w2,from_peak_id=p['peak_id'] if side=='from' else None,
                                  to_peak_id=p['peak_id'] if side=='to' else None, matching_status='UNMATCHED_'+side.upper(), physical_identity_confirmed=False))
    return edges


def analyze(out):
    package = json.loads((out/'config.json').read_text(encoding='utf-8'))
    settings,cfg = package['settings'],package['optical_config']
    images,peaks,records = {},{},{}
    rows,main_intervals,branches = [],[],[]
    sources = json.loads((out/'sources.json').read_text(encoding='utf-8'))
    for w in sorted(int(k) for k in sources):
        raw,c,r = load(out/'cases'/f'A2_m12_{w}.npz')
        measured = old.lobe_record(raw,c,r,cfg,w)
        assert measured['status']==r['status']
        images[w] = raw
        records[w] = measured
        peaks[w] = extract(raw,c,measured,cfg,settings,w)
        for row in peaks[w]: row['source'] = sources[str(w)]['source']
        rows.extend(peaks[w])
    waves = settings['diagnostic_waves_nm']
    for a,b in zip(waves,waves[1:]):
        branches.extend(edges_for(a,b,peaks,images,settings['peak_analysis']))
        p,q = peaks[a][0],peaks[b][0]
        delta = angle_delta(p['angle_deg'],q['angle_deg'])
        main_intervals.append(dict(from_nm=a,to_nm=b,brightest_angle_delta_deg=delta,brightest_radial_delta_um=q['r_um']-p['r_um'],
                                   brightest_spatial_distance_um=math.hypot(q['x_um']-p['x_um'],q['y_um']-p['y_um']),
                                   tangential_arc_um=(q['r_um']+p['r_um'])/2*math.radians(abs(delta)),
                                   pixel_fit_angle_diagnostic_margin_deg=p['angle_pixel_fit_offset_deg']+q['angle_pixel_fit_offset_deg'],
                                   both_original_valid=records[a]['recognizable_single_lobe'] and records[b]['recognizable_single_lobe'],
                                   is_single_physical_branch_proven=False))
    write_csv(out/'peak_metrics.csv', rows)
    write_csv(out/'branch_tracking.csv', branches)
    write_json(out/'peak_metrics.json', rows)
    write_json(out/'branch_tracking.json', branches)
    evidence = []
    for a,b in zip(waves,waves[1:]):
        links = [e for e in branches if e['wavelength_from_nm']==a and e['wavelength_to_nm']==b]
        mainlinks = [e for e in links if e.get('from_rank')==e.get('to_rank')==1]
        evidence.append(dict(from_nm=a,to_nm=b,brightest_to_brightest_feasible=bool(mainlinks),
                             main_link_status=mainlinks[0]['matching_status'] if mainlinks else 'NOT_FEASIBLE_WITHIN_GATES',
                             brightest_from_to_rank=[e.get('to_rank') for e in links if e.get('from_rank')==1],
                             brightest_to_from_rank=[e.get('from_rank') for e in links if e.get('to_rank')==1],
                             total_ambiguous_edges=sum(e['matching_status']=='AMBIGUOUS_MULTIPLE' for e in links)))
    analysis = dict(scientific_conclusion='INCONCLUSIVE', identity_switch_directly_proven=False,
                    interpretation='存在多峰竞争及最亮峰角度非单调，候选对应受匹配门限与25nm采样限制；不把候选连接解释为唯一物理衍射分支。',
                    unwrap_rule='仅最短有符号角差[-180,180)，逐相邻25nm点；不通过任意加减360度制造单调性。无效峰只作最亮峰几何诊断，不纳入有效旋转。',
                    brightest_peak_intervals=main_intervals, candidate_link_evidence=evidence,
                    coordinate_and_angle_precision='3x3局部拟合与像素峰位置偏差仅是诊断量，无新收敛/误差标定，不能据小角差认定符号。',
                    plateau_endpoints=dict(from_nm=550,to_nm=600, radial_delta_um=peaks[600][0]['r_um']-peaks[550][0]['r_um'],
                                           angle_delta_deg=angle_delta(peaks[550][0]['angle_deg'],peaks[600][0]['angle_deg']),
                                           note='须同时检查575nm中间点，不用端点近相同角度代替整段运动。'))
    write_json(out/'rotation_analysis.json',analysis)
    plot(out,images,peaks,branches,records,waves)
    print('最亮峰序列：',[(w,round(peaks[w][0]['angle_deg'],5),round(peaks[w][0]['r_um'],5),records[w]['status'],round(peaks[w][0]['strongest_competitor_relative_height'],4)) for w in waves],flush=True)
    print('候选匹配诊断：',json.dumps(evidence,ensure_ascii=False),flush=True)


def plot(out,images,peaks,branches,records,waves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    vmax=max(images[w].max() for w in waves)
    fig,axes=plt.subplots(2,4,figsize=(16,8),layout='constrained')
    for ax,w in zip(axes.flat,waves):
        im=ax.imshow(images[w],origin='lower',extent=[-256,256,-256,256],cmap='inferno',vmin=0,vmax=vmax,interpolation='nearest')
        ax.set(title=f'{w}nm / {records[w]["status"]}',xlabel='x (um)',ylabel='y (um)')
        inset=ax.inset_axes([.04,.04,.45,.45])
        inset.imshow(images[w],origin='lower',extent=[-256,256,-256,256],cmap='inferno',vmin=0,vmax=vmax,interpolation='nearest')
        inset.set(xlim=(-45,45),ylim=(-45,45),xticks=[],yticks=[])
        inset.set_title('+/-45um; same scale',fontsize=6,color='cyan',pad=1)
        for p in peaks[w][:4]:
            inset.plot(p['x_um'],p['y_um'],'+',ms=4,color='cyan' if p['rank']==1 else 'lime')
    axes.flat[-1].axis('off')
    fig.colorbar(im,ax=list(axes.flat),label='Raw intensity (um^-2), common linear scale; input energy=1',shrink=.7)
    fig.suptitle('A2-m12 abnormal bands: full fixed ROI; brightest and competing peaks')
    fig.savefig(out/'psf_comparison.png',dpi=150)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(15,6),layout='constrained')
    colors=plt.cm.viridis(np.linspace(0,1,len(waves)))
    lookup={p['peak_id']:p for w in waves for p in peaks[w]}
    for ax in axes:
        for e in branches:
            if not e.get('from_peak_id') or not e.get('to_peak_id'): continue
            a,b=lookup[e['from_peak_id']],lookup[e['to_peak_id']]
            if max(a['rank'],b['rank'])>6: continue
            ax.plot([a['x_um'],b['x_um']],[a['y_um'],b['y_um']],linestyle=':' if e['matching_status']=='AMBIGUOUS_MULTIPLE' else '--',lw=.6,color='gray',alpha=.35)
        for color,w in zip(colors,waves):
            ps=peaks[w]
            ax.scatter([p['x_um'] for p in ps],[p['y_um'] for p in ps],s=[25+75*p['relative_to_brightest'] for p in ps],color=color,label=f'{w}nm',alpha=.7)
            p=ps[0]
            ax.plot(p['x_um'],p['y_um'],'*',ms=13,color=color,markeredgecolor='black')
            ax.annotate(str(w),(p['x_um'],p['y_um']),fontsize=7)
        ax.set(aspect='equal',xlabel='x (um)',ylabel='y (um)')
        ax.grid(alpha=.2)
    axes[0].set(xlim=(-60,60),ylim=(-60,60),title='Candidate graph (rank<=6 links); stars=independent brightest')
    axes[1].set(xlim=(-30,30),ylim=(-15,35),title='Same origin, detail: dotted=ambiguous, dashed=unique within gates')
    axes[0].legend(fontsize=8)
    fig.savefig(out/'peak_trajectory.png',dpi=160)
    plt.close(fig)


if __name__=='__main__': analyze(Path(sys.argv[1]).resolve())
