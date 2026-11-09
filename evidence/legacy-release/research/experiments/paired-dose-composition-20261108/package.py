#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,zipfile
R=Path(__file__).resolve().parent
skip={'MANIFEST.json','audit-bundle.zip','archive-integrity.json'}
files=[p for p in sorted(R.rglob('*')) if p.is_file() and str(p.relative_to(R)) not in skip and '__pycache__' not in p.parts]
manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(R/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(R/'audit-bundle.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files+[R/'MANIFEST.json']:z.write(p,str(p.relative_to(R)))
with zipfile.ZipFile(R/'audit-bundle.zip') as z:
 assert z.testzip() is None
 for name,h in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
report={'status':'pass','files':len(files),'zip_bytes':(R/'audit-bundle.zip').stat().st_size,'sha256':hashlib.sha256((R/'audit-bundle.zip').read_bytes()).hexdigest(),'scope':'Analysis code/results/report only; prior evidence dependencies are not duplicated. See README.txt.'}
(R/'archive-integrity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
