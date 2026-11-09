"""Archived data -> analyses -> figures -> complete bilingual article; no simulation."""
from pathlib import Path
import argparse,subprocess,sys,os,json,zipfile,shutil,hashlib
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--plot-python',required=True);a=p.parse_args()
if a.output_dir.exists():raise SystemExit('Choose a new output directory; frozen releases are never overwritten.')
a.output_dir.mkdir(parents=True)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(a.output_dir/'plot-cache'))
def run(args):subprocess.run([str(x) for x in args],check=True,env=env)
# The original release rebuild regenerates score ablations, paired doses and input
# controls from archived trajectories. Its default path does not run simulations.
run([sys.executable,'-B',R/'evidence/legacy-release/reproduce_current.py','--simulation-python',a.plot_python,'--output-dir',a.output_dir/'legacy'])
run([sys.executable,'-B',R/'reanalyze.py','--output-dir',a.output_dir/'analysis'])
figs=a.output_dir/'manuscript/figures';shutil.copytree(a.output_dir/'legacy/figures',figs)
run([a.plot_python,'-B',R/'plot_paper.py','--analysis',a.output_dir/'analysis','--output-dir',figs])
for lang in ['en','zh']:
 run([sys.executable,'-B',R/'manuscript/build_preprint.py',lang,'--analysis',a.output_dir/'analysis','--figures-dir',figs,'--score-audit-dir',a.output_dir/'legacy/score','--dose-dir',a.output_dir/'legacy/dose','--input-control-dir',a.output_dir/'legacy/input','--output-dir',a.output_dir/'manuscript'])
checks={}
for f in sorted((R/'analysis').iterdir()):
 if f.suffix in ['.csv','.json']:
  assert f.read_bytes()==(a.output_dir/'analysis'/f.name).read_bytes(),f.name;checks['analysis/'+f.name]='byte-identical'
for f in sorted(figs.glob('*.png')):
 assert f.read_bytes()==(R/'manuscript/figures'/f.name).read_bytes(),f.name;checks['figures/'+f.name]='byte-identical'
for lang in ['en','zh']:
 name=f'input-and-horizon-dependent-structural-fidelity-preprint-{lang}.docx'
 with zipfile.ZipFile(R/'manuscript'/name) as old,zipfile.ZipFile(a.output_dir/'manuscript'/name) as new:
  assert set(old.namelist())==set(new.namelist())
  for part in old.namelist():assert old.read(part)==new.read(part),(name,part)
 checks[name]='all OOXML and media members identical (ZIP timestamps ignored)'
report=dict(status='pass',analysis_only=True,new_scientific_simulations=0,new_radius_queries=0,checks=checks,legacy_reanalysis=json.loads((a.output_dir/'legacy/reproduction.json').read_text()),python=sys.version,plot_python=a.plot_python)
(a.output_dir/'rebuild-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='legacy_reanalysis'},indent=2))
