"""Recreate the English editable document locally; no simulation or remote upload."""
from pathlib import Path
import json,hashlib,zipfile,subprocess,sys,tempfile,shutil
R=Path(__file__).resolve().parent
expected=json.loads((R/'validation/english-docx-member-sha256.json').read_text())
with tempfile.TemporaryDirectory(prefix='structural-fidelity-docx-') as tmp:
 subprocess.run([sys.executable,str(R/'manuscript/build_preprint.py'),'en','--output-dir',tmp],check=True)
 p=Path(tmp)/'input-and-horizon-dependent-structural-fidelity-preprint-en.docx'
 with zipfile.ZipFile(p) as z:
  actual={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}
 assert actual==expected,'Document members differ from the reviewed local Word file.'
 shutil.copy2(p,R/'manuscript'/p.name)
print('English Word rebuilt locally; all OOXML/media member hashes match. No upload or simulation.')
