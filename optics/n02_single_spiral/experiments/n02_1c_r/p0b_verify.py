"""只读复核本轮诊断归档，禁止修改旧Gate或写回任何文件。"""
import sys
sys.dont_write_bytecode=True
import argparse
import json
from p0b_common import *
from p0b_locators import quadratic
from p0b_analysis import gram_diagnostics


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    out=ROOT/'results/n02_1c_r'/args.run_id;m=read(out/'manifest.json');hashes=read(out/'artifact_manifest.json')
    assert sha(out/'artifact_manifest.json')==m['artifact_manifest_sha256']
    for p,h in hashes.items():assert sha(out/p)==h,f'产物SHA失败：{p}'
    for p,h in m['source_hashes'].items():assert sha(ROOT/p)==h,f'源码SHA失败：{p}'
    inputs=read(out/'input_hashes.json')
    for p,h in inputs.items():assert sha(p)==h,f'输入SHA失败：{p}'
    a,c,r=loadcase(OLD/'B2/cases/425nm.npz');q=quadratic(a,c)
    ref=csvread(out/'diagnostics/425_fit_audit.csv')[0]
    assert np.allclose(q['unconstrained_offset_pixels'],json.loads(ref['unconstrained_offset_pixels']),atol=1e-12,rtol=0)
    columns=[loadcase(OLD/'B2/cases'/f'{w}nm.npz')[0].ravel() for w in range(420,661,10)]
    gram,eig,stats=gram_diagnostics(columns)
    z=np.load(out/'diagnostics/gram_pixel1um.npz',allow_pickle=False)
    assert np.max(abs(gram-z['gram']))<1e-12
    assert read(OLD/'gates.json')['G2']['status']==read(OLD/'gates.json')['G3_Numerics']['status']=='FAIL'
    assert read(out/'P0B_gate_decision.json')['G4_G8']=='NOT_TESTED_DO_NOT_START'
    starts=[json.loads(s) for s in (out/'execution_ledger.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    starts=[r for r in starts if r['event']=='ASM_START'];assert len(starts)<=12
    assert all(r['wavelength_nm'] in list(range(420,431))+[546.1,660] for r in starts)
    cfg,h,d=pupil();hd=arrsha(h)
    for p in (out/'propagation').glob('ASM_*.npz'):
        a,c,r=loadcase(p);assert r['height_array_sha256']==hd
        assert np.isclose(a.sum(),r['crop_energy'],rtol=0,atol=1e-12)
    print(json.dumps(dict(status='PASS',output_hashes=len(hashes),input_hashes=len(inputs),new_ASM_calls=len(starts),
        independent_425_fit_reproduced=True,Gram_recomputed=True,old_G2_G3='FAIL_UNCHANGED',
        decision=read(out/'P0B_gate_decision.json')['status']),ensure_ascii=False,indent=2))
