"""只读复用原传播/检测纯函数，写入限定新阶段。"""
import sys
sys.dont_write_bytecode=True
import importlib.util
from pathlib import Path
import os
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
EXP=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'experiments/N01_2E_multiorder_pilot'))
spec=importlib.util.spec_from_file_location('g2_legacy_tools',ROOT/'experiments/N01_2E_multiorder_pilot/run.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
legacy=old.legacy
sha,write_json,write_csv,save_case=old.sha,old.write_json,old.write_csv,old.save_case


def load(path):
    with np.load(path,allow_pickle=False) as z:return z['raw_roi'].copy(),z['coords_um'].copy(),json.loads(z['record_json'].item())


def protection():
    result={}
    for current,dirs,files in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in ['.git','N01_2F_G2_f1_13wave']]
        for name in files:
            p=Path(current)/name;s=p.stat();r=dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns)
            if p.suffix.lower() in ['.py','.json','.csv','.md','.txt']:r['sha256']=sha(p)
            result[p.relative_to(ROOT).as_posix()]=r
    return result


def add_competition(r):
    r=dict(r)
    r.update(competitor_relative_height=1/r['distinct_side_ratio'] if r['distinct_side_ratio'] else None,
             independent_peak_gap_raw=r['main_peak']-r['distinct_side_peak'],
             independent_peak_gap_fraction=1-1/r['distinct_side_ratio'] if r['distinct_side_ratio'] else None,
             ROI99='PASS' if r['crop_fraction']>=.99 else 'FAIL')
    return r


def rotation(rows,cfg):
    intervals=[];segment=-1;previous=None
    for r in rows:
        r['angle_unwrapped_deg']=None;r['rotation_segment']=None
        if r['recognizable_single_lobe']:
            delta=None;ambiguous=True
            if previous is not None and previous['recognizable_single_lobe']:
                delta=(r['angle_raw_deg']-previous['angle_raw_deg']+180)%360-180
                margin=r['pixel_fit_angle_offset_deg']+previous['pixel_fit_angle_offset_deg']
                ambiguous=abs(delta)>cfg['thresholds']['dense_step_deg'] or abs(delta)<=margin
            if delta is None or ambiguous:
                segment+=1;r['angle_unwrapped_deg']=r['angle_raw_deg']
            else:r['angle_unwrapped_deg']=previous['angle_unwrapped_deg']+delta
            r['rotation_segment']=segment
        if previous is not None:
            both=bool(r['recognizable_single_lobe'] and previous['recognizable_single_lobe'])
            delta=(r['angle_raw_deg']-previous['angle_raw_deg']+180)%360-180 if both else None
            margin=r['pixel_fit_angle_offset_deg']+previous['pixel_fit_angle_offset_deg'] if both else None
            ambiguous=bool(both and (abs(delta)>cfg['thresholds']['dense_step_deg'] or abs(delta)<=margin))
            intervals.append(dict(from_nm=previous['wavelength_nm'],to_nm=r['wavelength_nm'],both_valid=both,
                                  shortest_delta_angle_deg=delta,radial_delta_um=r['peak_radius_um']-previous['peak_radius_um'] if both else None,
                                  diagnostic_pixel_fit_angle_margin_deg=margin,branch_ambiguous=ambiguous,
                                  spatial_peak_distance_um=float(np.hypot(r['peak_x_um']-previous['peak_x_um'],r['peak_y_um']-previous['peak_y_um'])),
                                  status='INVALID_ENDPOINT' if not both else 'INCONCLUSIVE' if ambiguous else 'DECREASE' if delta<0 else 'INCREASE',
                                  physical_peak_identity_proven=False))
        previous=r
    valid=all(r['recognizable_single_lobe'] for r in rows)
    reliable=[r['shortest_delta_angle_deg'] for r in intervals if r['both_valid'] and not r['branch_ambiguous']]
    sign_reversal=any(d<0 for d in reliable) and any(d>0 for d in reliable)
    noamb=all(r['both_valid'] and not r['branch_ambiguous'] for r in intervals)
    monotone=valid and noamb and (all(d<0 for d in reliable) or all(d>0 for d in reliable))
    science='FAIL' if not valid or sign_reversal else 'PASS' if monotone else 'INCONCLUSIVE'
    return intervals,dict(scientific_status=science,all_13_valid=valid,valid_count=sum(r['recognizable_single_lobe'] for r in rows),
                          credible_opposite_sign_intervals=sign_reversal,monotonic_at_13_samples=monotone,
                          sampled_rotation_status='PASS_WITH_LIMITATIONS' if monotone else 'FAIL' if valid and sign_reversal else 'INCONCLUSIVE',
                          full_band_rotation_certified=False,spectral_resolution_certified=False,
                          total_rotation_deg=rows[-1]['angle_unwrapped_deg']-rows[0]['angle_unwrapped_deg'] if monotone else None)
