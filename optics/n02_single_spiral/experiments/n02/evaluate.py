"""独立回读原始PSF，继承冻结检测和链接，补充新指标。"""
import sys
sys.dont_write_bytecode = True
import csv
import json
import math
from pathlib import Path
import numpy as np
from optics import *
from audit import write, textfile


def csvwrite(path, rows):
    path = Path(path)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x',encoding='utf-8-sig',newline='') as f:
        w = csv.DictWriter(f,fieldnames=keys)
        w.writeheader()
        w.writerows([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows])


def load(path):
    with np.load(path,allow_pickle=False) as z:
        return z['raw_roi'].copy(),z['coords_um'].copy(),json.loads(z['record_json'].item())


def evaluate(folder, cfg, waves, tag='standard'):
    cfgold=dict(diameter_um=2*cfg['R_um'], sensor_mm=cfg['sensor_mm'], pitch_um=cfg['pitch_um'],
                roi_width_um=cfg['roi_width_um'],thresholds=cfg['thresholds'])
    params=json.loads((folder.parent/'protocol_frozen.json').read_text(encoding='utf-8'))['peak_analysis']
    rows=[]; images={}; peaks={}; allpeaks=[]
    for w in waves:
        raw,c,rec=load(folder/'cases'/f'{w:g}nm.npz')
        r=measure(raw,c,rec,cfg,w)
        assert r['status']==rec['status'] and r['halfmax_components']==rec['halfmax_components']
        r['source_sha256']=sha(folder/'cases'/f'{w:g}nm.npz')
        images[w]=raw
        if cfg['pitch_um']==1.:
            peaks[w]=p3.extract(raw,c,r,cfgold,dict(peak_analysis=params),w)
            allpeaks.extend(peaks[w])
        rows.append(r)
    intervals=[]; edges=[]
    for w1,w2 in zip(waves,waves[1:]):
        a=next(r for r in rows if r['wavelength_nm']==w1)
        b=next(r for r in rows if r['wavelength_nm']==w2)
        ee=p3.edges_for(w1,w2,peaks,images,params) if peaks else []
        edges.extend(ee)
        main=[e for e in ee if e.get('from_rank')==e.get('to_rank')==1]
        unique=bool(main and main[0]['matching_status']=='UNIQUE_WITHIN_GATES')
        delta=(b['raw_angle_deg']-a['raw_angle_deg']+180)%360-180
        margin=a['pixel_fit_angle_error_proxy_deg']+b['pixel_fit_angle_error_proxy_deg']
        reasons=[]
        if a['n01_status']!='VALID' or b['n01_status']!='VALID':reasons.append('INVALID_ENDPOINT')
        if not unique:reasons.append('MAIN_LINK_NOT_UNIQUE')
        if abs(delta)>45:reasons.append('OLD_ANGLE_GT_45')
        if abs(delta)<=margin:reasons.append('ANGLE_SIGN_UNCERTAIN_PROXY')
        if peaks and ((peaks[w1][0]['strongest_competitor_relative_height']>=.8)!=(peaks[w2][0]['strongest_competitor_relative_height']>=.8)):
            reasons.append('COMPETITION_CROSSES_08')
        distance=math.hypot(b['peak_x_um']-a['peak_x_um'],b['peak_y_um']-a['peak_y_um'])
        if distance>15:reasons.append('DISTANCE_GT_15UM')
        if abs(b['radius_um']-a['radius_um'])>6:reasons.append('RADIAL_GT_6UM')
        patch=p3.patch_cosine(images[w1],peaks[w1][0],images[w2],peaks[w2][0],10) if peaks else None
        factor=max(a['main_peak']/b['main_peak'],b['main_peak']/a['main_peak'])
        if patch is None or patch<.65:reasons.append('PATCH_COSINE_LT_065_OR_MISSING')
        if abs(delta)>70:reasons.append('ANGLE_GT_70DEG')
        if factor>4:reasons.append('INTENSITY_FACTOR_GT_4')
        lo=4*(w2-w1)/10; hi=18*(w2-w1)/10
        intervals.append(dict(from_nm=w1,to_nm=w2,delta_angle_deg=delta,delta_nm=w2-w1,
            min_scaled_deg=lo,max_scaled_deg=hi,n02_angle_gate=lo<=abs(delta)<=hi,
            main_link_status='MAIN_LINK_UNIQUE_WITHIN_GATES' if unique else 'MAIN_LINK_AMBIGUOUS_OR_REJECTED',
            main_link_unique=unique,credible=not reasons,reason=';'.join(reasons),
            spatial_distance_um=distance,patch_cosine=patch,intensity_factor=factor,
            angle_error_proxy_deg=margin,physical_identity_confirmed=False))
    diag=np.rad2deg(np.unwrap(np.deg2rad([r['raw_angle_deg'] for r in rows])))
    segment=-1; prev=None; direction=None
    for i,r in enumerate(rows):
        r['diagnostic_unwrapped_angle_deg']=float(diag[i])
        r['unwrapped_angle_deg']=None;r['main_link_status']='NO_PREVIOUS';r['delta_angle_deg']=None
        r['psf_corr_adjacent']=None;r['psf_pearson_adjacent']=None
        if i:
            it=intervals[i-1]
            r['main_link_status']=it['main_link_status'];r['delta_angle_deg']=it['delta_angle_deg']
            a=images[waves[i-1]].ravel();b=images[waves[i]].ravel()
            r['psf_corr_adjacent']=float(a@b/np.linalg.norm(a)/np.linalg.norm(b))
            r['psf_pearson_adjacent']=float(np.corrcoef(a,b)[0,1])
        if r['n01_status']!='VALID':prev=None;direction=None;rows[i]['angle_segment']=None;continue
        it=intervals[i-1] if i else None
        sign=np.sign(it['delta_angle_deg']) if it else None
        connected=bool(prev is not None and it['credible'] and (direction is None or direction==sign))
        if connected:
            r['unwrapped_angle_deg']=prev['unwrapped_angle_deg']+it['delta_angle_deg'];direction=sign
        else:
            segment+=1;r['unwrapped_angle_deg']=r['raw_angle_deg'];direction=None
        r['angle_segment']=segment;prev=r
    X=np.stack([images[w].ravel() for w in waves],axis=1)
    X/=np.linalg.norm(X,axis=0)
    gram=X.T@X; eig=np.linalg.eigvalsh(gram).clip(0); probs=eig/eig.sum()
    summary=dict(candidate_id=cfg['candidate_id'],wave_count=len(waves),n01_valid=sum(r['n01_status']=='VALID' for r in rows),
        n02_valid=sum(r['n02_status']=='PASS' for r in rows),single_component_count=sum(r['halfmax_components']==1 for r in rows),
        unique_main_links=sum(it['main_link_unique'] for it in intervals),credible_links=sum(it['credible'] for it in intervals),
        diagnostic_rotation_deg=float(diag[-1]-diag[0]),rotation_deg=None,
        min_outside_ratio=min(r['main_sidelobe_ratio'] for r in rows),mean_outside_ratio=float(np.mean([r['main_sidelobe_ratio'] for r in rows])),
        min_distinct_ratio=min(r['distinct_side_ratio'] for r in rows if r['distinct_side_ratio'] is not None),
        min_roi_fraction=min(r['crop_fraction'] for r in rows),max_roi_fraction=max(r['crop_fraction'] for r in rows),
        min_main_incident_fraction=min(r['main_lobe_energy_fraction'] for r in rows),
        mean_main_incident_fraction=float(np.mean([r['main_lobe_energy_fraction'] for r in rows])),
        min_radius_um=min(r['radius_um'] for r in rows),max_radius_um=max(r['radius_um'] for r in rows),
        radius_cv=float(np.std([r['radius_um'] for r in rows])/np.mean([r['radius_um'] for r in rows])),
        gram_condition_number=float(eig[-1]/max(eig[0],np.finfo(float).tiny)),
        effective_rank=float(np.exp(-np.sum(probs[probs>0]*np.log(probs[probs>0])))),
        max_adjacent_cosine=max((r['psf_corr_adjacent'] for r in rows if r['psf_corr_adjacent'] is not None),default=None),
        max_height_um=max(r['max_height_um'] for r in rows),
        failure_wavelengths_nm=[r['wavelength_nm'] for r in rows if r['n02_status']!='PASS'])
    ds=[it['delta_angle_deg'] for it in intervals]
    mono=bool(ds and (all(d>0 for d in ds) or all(d<0 for d in ds)))
    reliable=summary['n01_valid']==len(waves) and summary['credible_links']==len(intervals) and mono
    if reliable:summary['rotation_deg']=float(diag[-1]-diag[0])
    summary['monotone_brightest_diagnostic']=mono
    summary['G1_physical']='PASS' if all(np.isfinite(images[w]).all() and images[w].max()>0 and r['global_peak_in_roi'] for w,r in zip(waves,rows)) else 'FAIL'
    summary['G1_single_lobe']='PASS' if summary['n02_valid']==len(waves) else 'FAIL'
    summary['G1_monotone']='PASS' if reliable else 'FAIL'
    cumulative_ok=(200<=abs(summary['rotation_deg'])<=280) if tag=='standard' and summary['rotation_deg'] is not None else tag!='standard'
    summary['G2']='PASS' if (summary['n02_valid']==len(waves) and reliable and all(it['n02_angle_gate'] for it in intervals) and cumulative_ok) else 'FAIL'
    csvwrite(folder/f'{tag}_metrics.csv',rows);csvwrite(folder/f'{tag}_links.csv',intervals)
    if edges:csvwrite(folder/f'{tag}_all_edges.csv',edges)
    if allpeaks:csvwrite(folder/f'{tag}_all_peaks.csv',allpeaks)
    write(folder/f'{tag}_summary.json',summary)
    with (folder/f'{tag}_gram.npz').open('xb') as stream:
        np.savez_compressed(stream,gram=gram,wavelengths_nm=waves,eigenvalues=eig)
    return rows,intervals,summary,images


def plot_candidate(folder,rows,intervals,summary,images,tag='standard'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ws=list(images); vmax=max(images[w].max() for w in ws)
    for local in [False,True]:
        fig,axes=plt.subplots(5,5,figsize=(14,13),layout='constrained')
        for ax,(w,r) in zip(axes.ravel(),zip(ws,rows)):
            raw=images[w]
            ax.imshow(raw/(raw.max() if local else 1),origin='lower',extent=[-256,256,-256,256],cmap='inferno',vmin=0,vmax=1 if local else vmax)
            ax.set(xlim=(-100,100),ylim=(-100,100),title=f"{w:g}nm / {r['n02_status']}",xlabel='x (um)',ylabel='y (um)')
            ax.plot(r['peak_x_um'],r['peak_y_um'],'c+',ms=6)
        fig.suptitle(f"{summary['candidate_id']} / fixed height / ASM128 / dx=1um / pad2 / {'local peak scaled, morphology only' if local else 'common raw intensity um^-2'}; 420:10:660nm\nDisplay +/-100um; saved/evaluated ROI +/-256um; script experiments/n02/evaluate.py")
        fig.savefig(folder/f'psf25_{"local" if local else "common"}.png',dpi=130);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(16,9),layout='constrained')
    w=np.array([r['wavelength_nm'] for r in rows]); ang=np.array([r['diagnostic_unwrapped_angle_deg'] for r in rows])
    axes[0,0].plot([r['peak_x_um'] for r in rows],[r['peak_y_um'] for r in rows],'o-');axes[0,0].set(xlabel='x (um)',ylabel='y (um)',title='Brightest peak position; identity conditional');axes[0,0].axis('equal')
    axes[0,1].plot(w,ang,'o-',label='diagnostic brightest unwrap')
    predicted=45*cfg_nf(config())*(546.1/420-546.1/w)
    if len(ang)>1 and ang[-1]<ang[0]:predicted=-predicted
    axes[0,1].plot(w,ang[0]+predicted,'--',label='DERIVED approximation, anchored at 420nm')
    axes[0,1].set(xlabel='Wavelength (nm)',ylabel='Angle (deg)',title='Not identity proof');axes[0,1].legend(fontsize=7)
    axes[0,2].plot([(i['from_nm']+i['to_nm'])/2 for i in intervals],[i['delta_angle_deg'] for i in intervals],'o-');axes[0,2].axhline(4,color='gray');axes[0,2].axhline(18,color='gray');axes[0,2].set(xlabel='Wavelength (nm)',ylabel='Delta (deg / 10nm)')
    axes[1,0].plot(w,[r['outside_main_disk_ratio'] for r in rows],label='peak/outside disk');axes[1,0].plot(w,[r['distinct_side_ratio'] for r in rows],label='peak/distinct side');axes[1,0].axhline(1.5,color='r');axes[1,0].axhline(1.25,color='gray');axes[1,0].legend();axes[1,0].set(xlabel='Wavelength (nm)',ylabel='Intensity ratio')
    axes[1,1].plot(w,[r['roi_energy_fraction'] for r in rows],label='ROI / incident');axes[1,1].plot(w,[r['main_lobe_energy_fraction'] for r in rows],label='disk / incident');axes[1,1].legend();axes[1,1].set(xlabel='Wavelength (nm)',ylabel='Energy fraction')
    g=np.load(folder/f'{tag}_gram.npz')['gram']; im=axes[1,2].imshow(g,origin='lower',extent=[ws[0]-5,ws[-1]+5,ws[0]-5,ws[-1]+5],vmin=0,vmax=1);fig.colorbar(im,ax=axes[1,2]);axes[1,2].set(xlabel='Wavelength (nm)',ylabel='Wavelength (nm)',title='Uncentered L2 Gram')
    fig.suptitle(f"{summary['candidate_id']} / SIMULATED / ASM128 dx1um pad2 / scripts experiments/n02/evaluate.py")
    fig.savefig(folder/'metrics_trajectory_gram.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(13,8),layout='constrained')
    for ax,w in zip(axes.ravel(),[420,460,500,546.1,600,660]):
        raw,c,r=load(folder/'cases'/f'{w:g}nm.npz')
        ax.imshow(raw,origin='lower',extent=[-256,256,-256,256],cmap='inferno');ax.set(xlim=(-80,80),ylim=(-80,80),xlabel='x (um)',ylabel='y (um)',title=f"{w:g} nm; {r['n02_status']}")
        ax.plot(r['peak_x_um'],r['peak_y_um'],'c+')
    fig.suptitle(f"{summary['candidate_id']} / raw intensity local scale / ASM128 dx1um pad2 / fixed height")
    fig.savefig(folder/'six_wavelength_details.png',dpi=140);plt.close(fig)


def cfg_nf(cfg):
    return cfg['R_um']**2/(2*(cfg['design_nm']/1000)*cfg['focal_mm']*1000)
