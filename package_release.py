"""Package current manuscripts and immutable evidence; no scientific execution."""
from pathlib import Path
import zipfile,json,hashlib,time
R=Path(__file__).resolve().parent
ARCHIVE='input-and-horizon-dependent-structural-fidelity-source-and-evidence.zip'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def include(p):
 x=p.relative_to(R)
 if len(x.parts)==1 and x.name in [ARCHIVE,'package-sha256.json','archive-integrity.json']:return False
 if x.parts[0]=='validation' and len(x.parts)>2:return False
 if x.parts[0]!='evidence' and ('__pycache__' in x.parts or x.suffix=='.pyc'):return False
 return True
files=sorted(p for p in R.rglob('*') if p.is_file() and include(p))
manifest={str(p.relative_to(R)):sha(p) for p in files}
(R/'package-sha256.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
with zipfile.ZipFile(R/ARCHIVE,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for p in files+[R/'package-sha256.json']:z.write(p,p.relative_to(R))
with zipfile.ZipFile(R/ARCHIVE) as z:
 assert z.testzip() is None
 assert set(z.namelist())==set(manifest)|{'package-sha256.json'}
 for name,h in manifest.items():
  hh=hashlib.sha256()
  with z.open(name) as f:
   while b:=f.read(1024*1024):hh.update(b)
  assert hh.hexdigest()==h,name
 assert json.loads(z.read('package-sha256.json'))==manifest
report=dict(status='pass',archive=ARCHIVE,archive_sha256=sha(R/ARCHIVE),archive_bytes=(R/ARCHIVE).stat().st_size,manifest_files=len(manifest),crc_checked=True,all_member_hashes_checked=True,exclusions='Root archive/self-manifest/integrity report; temporary current page renders and caches. Evidence retained intact.')
(R/'archive-integrity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
