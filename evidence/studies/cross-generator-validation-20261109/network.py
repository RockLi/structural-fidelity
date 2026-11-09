from pathlib import Path
import hashlib,json,os
ROOT=Path(os.environ['NB_GRAPH_ROOT']).resolve();STUDY=Path(__file__).resolve().parent
def check():
 for name,h in json.loads((STUDY/'design-lock.json').read_text())['files'].items():
  assert hashlib.sha256((STUDY/name).read_bytes()).hexdigest()==h,name
 for name,h in json.loads((STUDY/'dependencies.json').read_text()).items():
  assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
