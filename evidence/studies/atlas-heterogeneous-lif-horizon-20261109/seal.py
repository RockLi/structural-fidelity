from pathlib import Path
import hashlib,json,sys,datetime
R=Path(__file__).resolve().parent
SKIP={'.venv','__pycache__','tmp','.DS_Store','MANIFEST.json','MANIFEST.sha256'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def inventory():return {str(p.relative_to(R)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(R.rglob('*')) if p.is_file() and not set(p.relative_to(R).parts)&SKIP}
if len(sys.argv)>1 and sys.argv[1]=='verify':
 m=json.loads((R/'MANIFEST.json').read_text());assert sha(R/'MANIFEST.json')==(R/'MANIFEST.sha256').read_text().split()[0];assert inventory()==m['files'];print('MANIFEST VERIFIED',len(m['files']))
else:
 assert not (R/'MANIFEST.json').exists(),'Already sealed; use verify'
 f=inventory();(R/'MANIFEST.json').write_text(json.dumps(dict(sealed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files_count=len(f),total_bytes=sum(x['bytes'] for x in f.values()),excluded=sorted(SKIP),files=f),indent=2)+'\n');(R/'MANIFEST.sha256').write_text(sha(R/'MANIFEST.json')+'  MANIFEST.json\n');print('SEALED',len(f),'files',sum(x['bytes'] for x in f.values()),'bytes')
