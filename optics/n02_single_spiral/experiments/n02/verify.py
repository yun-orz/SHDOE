"""只读交付复核：不重跑传播，不写入或覆盖任何科研证据。"""
import sys
sys.dont_write_bytecode=True
import argparse
import json
import numpy as np
from optics import ROOT,sha,measure,array_sha
from evaluate import load


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    out=ROOT/'results/n02'/args.run_id
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    files=json.loads((out/'artifact_manifest.json').read_text(encoding='utf-8'))
    assert sha(out/'artifact_manifest.json')==manifest['artifact_manifest_sha256']
    for name,digest in files.items():assert sha(out/name)==digest,f'产物哈希不一致：{name}'
    for name,digest in manifest['source_hashes'].items():assert sha(ROOT/name)==digest,f'源码哈希不一致：{name}'
    protection=json.loads((out/'preservation_comparison.json').read_text(encoding='utf-8'))
    assert protection['status']=='PASS' and protection['changed_original_paths']==[]
    verified=0
    for folder in out.iterdir():
        if not folder.is_dir() or not (folder/'config.json').exists():continue
        cfg=json.loads((folder/'config.json').read_text(encoding='utf-8'))
        height=np.load(folder/'height_um.npy',allow_pickle=False);digest=array_sha(height)
        for path in (folder/'cases').glob('*.npz'):
            raw,c,r=load(path)
            assert r['height_array_sha256']==digest
            rec=measure(raw,c,r,cfg,r['wavelength_nm'])
            assert rec['n01_status']==r['n01_status'] and rec['n02_status']==r['n02_status']
            assert np.isclose(raw.sum()*r['pitch_um']**2,r['crop_energy'],rtol=0,atol=1e-12)
            verified+=1
    gates=manifest['gates']
    assert gates['G2']['status']=='FAIL' and gates['G3_Numerics']['status']=='FAIL'
    assert all(gates[g]['execution']=='NOT_TESTED' for g in ['G4','G5','G6','G7','G8'])
    print(json.dumps(dict(verification='PASS',hash_verified_files=len(files),recomputed_cases=verified,
         engineering_verification_does_not_override_scientific_failure=True,gates=gates),ensure_ascii=False,indent=2))
