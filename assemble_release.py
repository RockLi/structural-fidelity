"""Verify numbered release parts and reconstruct the complete ZIP (stdlib only)."""
from pathlib import Path
import hashlib,json,os
R=Path(__file__).resolve().parent
m=json.loads((R/'release-checksums.json').read_text())
out=R/m['archive']['name']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
if out.exists():
 if out.stat().st_size==m['archive']['bytes'] and sha(out)==m['archive']['sha256']:
  print('Existing ZIP verified:',out.name);raise SystemExit(0)
 raise SystemExit('Refusing to overwrite an existing ZIP with a different checksum.')
for item in m['parts']:
 p=R/item['name']
 if not p.is_file() or p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
  raise SystemExit('Missing or corrupt part: '+p.name)
tmp=out.with_suffix('.zip.assembling')
h=hashlib.sha256()
with tmp.open('xb') as w:
 for item in m['parts']:
  with (R/item['name']).open('rb') as f:
   while b:=f.read(1024*1024):w.write(b);h.update(b)
if h.hexdigest()!=m['archive']['sha256'] or tmp.stat().st_size!=m['archive']['bytes']:
 raise SystemExit('Reassembled archive checksum mismatch; temporary file preserved.')
os.rename(tmp,out)
print('All parts and complete ZIP verified:',out.name)
