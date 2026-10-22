"""只读记录参考库，禁止导入其模块以避免生成缓存。"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT.parents[1]/'framework/DeepLensHSI'


def git(*args):
    return subprocess.check_output(['git', '-C', str(REF), *args]).decode('utf-8')


def snapshot():
    raise RuntimeError("历史快照工具已归档；请使用 provenance/tools 中的迁移审计入口，避免覆盖冻结证据。")
    files = {}
    for p in REF.rglob('*'):
        if not p.is_file() or '.git' in p.relative_to(REF).parts:
            continue
        rel = p.relative_to(REF).as_posix()
        stat = p.stat()
        entry = dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns)
        # 数据集不在本次写入路径内，仅记录尺寸与修改时间；其余文件全部哈希。
        if not rel.startswith('datasets/'):
            digest = hashlib.sha256()
            with p.open('rb') as stream:
                for chunk in iter(lambda: stream.read(8*1024*1024), b''):
                    digest.update(chunk)
            entry['sha256'] = digest.hexdigest()
        files[rel] = entry
    return dict(head=git('rev-parse', 'HEAD').strip(), status=git('status', '--porcelain=v1'),
                diff_sha256=hashlib.sha256(git('diff', '--binary', 'HEAD').encode()).hexdigest(),
                files=files, dataset_policy='仅 size/mtime；其他文件 SHA256')


if __name__ == '__main__':
    stage = argparse.ArgumentParser()
    stage.add_argument('stage', choices=['before','after'])
    name = stage.parse_args().stage
    out = ROOT / 'docs' / 'evidence'
    out.mkdir(parents=True, exist_ok=True)
    data = snapshot()
    (out / f'reference_{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    if name == 'after':
        previous = json.loads((out / 'reference_before.json').read_text(encoding='utf-8'))
        comparison = dict(unchanged=data == previous, file_count=len(data['files']),
                          hashed_file_count=sum('sha256' in v for v in data['files'].values()),
                          changed_files=[k for k in sorted(set(data['files'])|set(previous['files'])) if data['files'].get(k)!=previous['files'].get(k)],
                          git_unchanged=all(data[k]==previous[k] for k in ['head','status','diff_sha256']))
        (out / 'reference_comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
        print(comparison)
    else:
        print('前置快照文件数', len(data['files']))
