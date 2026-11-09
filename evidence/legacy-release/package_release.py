#!/usr/bin/env python3
"""Package the complete local release and verify every ZIP member checksum."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVE = 'local-circuit-preprint-source-and-evidence.zip'
MANIFEST = 'package-sha256.json'
REPORT = 'archive-integrity.json'
EXCLUDED = {ARCHIVE, MANIFEST, REPORT, 'archive-relocation.json'}
QA_DIRS = {'render-en','render-zh','final-en','final-zh','publication-en','publication-zh','publication-zh-v2'}
def internal_qa(path):
    parts = path.relative_to(ROOT).parts
    return len(parts)>1 and parts[0]=='validation' and parts[1] in QA_DIRS



def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024*1024), b''):
            result.update(data)
    return result.hexdigest()


def main():
    files = [p for p in sorted(ROOT.rglob('*')) if p.is_file()
             and not {'__pycache__', '.mpl-cache'} & set(p.relative_to(ROOT).parts)
             and p.suffix != '.pyc' and not internal_qa(p)
             and str(p.relative_to(ROOT)) not in EXCLUDED]
    manifest = {str(p.relative_to(ROOT)): sha(p) for p in files}
    (ROOT/MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    with zipfile.ZipFile(ROOT/ARCHIVE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files+[ROOT/MANIFEST]:
            archive.write(path, str(path.relative_to(ROOT)))
    with zipfile.ZipFile(ROOT/ARCHIVE) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(manifest) | {MANIFEST}
        assert json.loads(archive.read(MANIFEST)) == manifest
        for name, expected in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected, name
    report = dict(status='pass', archive=ARCHIVE, archive_bytes=(ROOT/ARCHIVE).stat().st_size,
                  archive_sha256=sha(ROOT/ARCHIVE), manifested_files=len(manifest),
                  zip_crc_checked=True, all_member_sha256_checked=True,
                  exclusions='Archive and its integrity sidecar; manifest does not hash itself; Python caches and internal page-render directories excluded')
    (ROOT/REPORT).write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
