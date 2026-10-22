"""一条命令先验证 T01–T04，然后执行正式导出及 T05–T06。"""
import csv
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import torch
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spiral_hsi.optics.psf import compute_psf,reference_doe


def main():
    cfg=yaml.safe_load((ROOT/'configs/n00_baseline.yaml').read_text(encoding='utf-8'))
    out=ROOT/'results/N00'
    # 已有交付物时拒绝覆盖，复跑请使用新的输出目录。
    if len(sys.argv)>1:
        if len(sys.argv)!=3 or sys.argv[1]!='--output':
            raise ValueError('仅支持 --output 新输出目录')
        out=Path(sys.argv[2]).resolve()
        if out.exists():
            raise FileExistsError('复跑输出目录必须尚不存在')
    if (out/'psf_cube.npz').exists():
        raise FileExistsError('已有正式产物，禁止覆盖；请通过 --output 指定新目录')
    test=subprocess.run([sys.executable,str(ROOT/'tests/run_all_tests.py')],capture_output=True,text=True)
    out.mkdir(parents=True,exist_ok=True)
    (out/'test_run.log').write_text(test.stdout+test.stderr,encoding='utf-8')
    print(test.stdout,flush=True)
    if test.returncode:
        raise RuntimeError('前置测试失败，正式导出停止；查看 preflight_summary.json')
    np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed'])
    h,a=reference_doe(cfg['size'],cfg['pitch_um'],cfg['radius_um'],cfg['focal_mm'],cfg['design_nm'])
    torch.cuda.reset_peak_memory_stats()
    start=time.perf_counter()
    r=compute_psf(h,cfg['wavelength_nm'],a,sampling_pitch_um=cfg['pitch_um'],propagation_distance_mm=cfg['focal_mm'],padding=cfg['padding'],crop=cfg['crop'],device=cfg['device'])
    elapsed=time.perf_counter()-start
    memory=dict(peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved())
    cube=r['PSF_cube']; stats=r['raw_energy_stats']
    assert cube.shape==(31,512,512) and np.array_equal(r['wavelength_nm'],np.arange(400,701,10))
    assert np.isfinite(cube).all() and cube.min()>=0
    norm_error=float(np.max(np.abs(cube.sum(axis=(1,2))-1)))
    assert norm_error<1e-12 and min(s['crop_fraction'] for s in stats)>.99
    assert max(s['energy_relative_error'] for s in stats)<1e-12
    assert max(s['edge_fraction'] for s in stats)<.001
    differences=[]
    for i,wave in enumerate(cfg['wavelength_nm']):
        repeated=compute_psf(h,[wave],a,sampling_pitch_um=cfg['pitch_um'],propagation_distance_mm=cfg['focal_mm'],padding=cfg['padding'],crop=cfg['crop'],device=cfg['device'])
        differences.append(float(np.max(np.abs(repeated['PSF_cube'][0]-cube[i]))))
    assert max(differences)<1e-12
    cpu=compute_psf(h,[550],a,device='cpu')
    cpu_gpu_error=float(np.max(np.abs(cpu['PSF_cube'][0]-cube[15])))
    assert cpu_gpu_error < 1e-10
    meta=r['metadata']
    meta.update(seed=cfg['seed'],config=cfg,python=platform.python_version(),torch=torch.__version__,numpy=np.__version__,
                gpu_name=torch.cuda.get_device_name(0),total_propagation_seconds=elapsed,**memory,
                model_boundary='薄相位标量模型；不包含偏振、吸收、制造误差、衍射效率及传感器颜色响应',
                reference_geometry='解析 N00 对照 D=128 µm，f=1 mm；不是旧库 4.096 mm 孔径的缩小替代',
                height_model='未包裹聚焦浮雕：h=(sqrt(f^2+R^2)-sqrt(f^2+r^2))/(n(550nm)-1)，孔径外 0',
                source_commit=json.loads((ROOT/'source_snapshot.json').read_text(encoding='utf-8'))['source_head'])
    x=(np.arange(512)-255.5)*cfg['pitch_um']
    raw_x=(np.arange(r['raw_intensity'].shape[2])-(r['raw_intensity'].shape[2]-1)/2)*cfg['pitch_um']
    raw_y=(np.arange(r['raw_intensity'].shape[1])-(r['raw_intensity'].shape[1]-1)/2)*cfg['pitch_um']
    np.savez_compressed(out/'psf_cube.npz',PSF_cube=cube,wavelength_nm=r['wavelength_nm'],height_um=h,
                        aperture_mask=a,x_um=x,y_um=x,raw_x_um=raw_x,raw_y_um=raw_y,raw_intensity=r['raw_intensity'])
    # 从文件重新读取，避免只验证内存而忽略交付格式。
    with np.load(out/'psf_cube.npz') as saved:
        assert np.array_equal(saved['PSF_cube'],cube) and np.array_equal(saved['wavelength_nm'],r['wavelength_nm'])
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'energy_and_crop.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(stats[0])); writer.writeheader(); writer.writerows(stats)
    fig,axes=plt.subplots(4,8,figsize=(18,9))
    for i,ax in enumerate(axes.flat):
        if i>=31:
            ax.set_visible(False); continue
        ax.imshow(np.log10(np.maximum(cube[i],cube[i].max()*1e-6)),extent=[-256,256,-256,256],origin='lower',cmap='magma')
        ax.set_xlim(-40,40); ax.set_ylim(-40,40); ax.set_title(f'{cfg["wavelength_nm"][i]} nm'); ax.set_xlabel('x (um)'); ax.set_ylabel('y (um)')
    fig.suptitle('Physical ASM PSF; log10 intensity display; full stored crop 512 um')
    fig.tight_layout(); fig.savefig(out/'psf_montage.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(); im=ax.imshow(h,extent=[-128,128,-128,128],origin='lower'); ax.set_xlabel('x (um)'); ax.set_ylabel('y (um)'); ax.set_title('Single fixed unwrapped relief height'); fig.colorbar(im,ax=ax,label='Height (um)'); fig.tight_layout(); fig.savefig(out/'height_map.png',dpi=160); plt.close(fig)
    summary=json.loads((ROOT/'results/N00/preflight_summary.json').read_text(encoding='utf-8'))
    summary['T05']=dict(status='PASS',shape=list(cube.shape),normalization_abs_error=norm_error,repeat_max_abs_errors=differences,cpu_gpu_abs_error=cpu_gpu_error,
                        crop_fraction_min=min(s['crop_fraction'] for s in stats),energy_relative_error_max=max(s['energy_relative_error'] for s in stats),export_reload_equal=True)
    summary['T06']=dict(status='PASS',device=meta['gpu_name'],total_seconds=elapsed,seconds_per_wavelength=[s['seconds'] for s in stats],**memory)
    (out/'test_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'T05':summary['T05'],'T06':summary['T06']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
