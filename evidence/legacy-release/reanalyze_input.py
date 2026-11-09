"""Regenerate input-control scores and summaries from immutable trajectories/radii."""
from pathlib import Path
import argparse,sys,shutil,runpy,json,hashlib
R=Path(__file__).resolve().parent;E=R/'research/experiments/input-control-directions-20261108'
p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args();out=args.output_dir.resolve();out.mkdir(exist_ok=False,parents=True)
sys.path.insert(0,str(E));import directions,common
# Only the score stage is called: no radius search or perturbed replay.
directions.score(E/'runs',out/'directions')
for name in ['radii.csv','queries.csv']:shutil.copy2(E/'directions'/name,out/'directions'/name)
for name in ['runs','events','graphs']:shutil.copytree(E/name,out/name)
for name in ['pool-lock.json','input-summary.csv','time-permutation.json']:shutil.copy2(E/name,out/name)
common.ROOT=out
for name in ['analyze_network.py','analyze_detail.py']:runpy.run_path(str(E/name),run_name='__main__')
sys.argv=[str(E/'analyze_directions.py'),'--results',str(out/'directions')];runpy.run_path(str(E/'analyze_directions.py'),run_name='__main__')
checks={}
for folder in [Path('.'),Path('directions')]:
 for f in sorted((out/folder).glob('*.csv')):
  old=E/folder/f.name;assert old.exists(),old
  checks[str(folder/f.name)]=f.read_bytes()==old.read_bytes();assert checks[str(folder/f.name)],f.name
for n in ['network-analysis.json','directions/analysis.json','directions/detailed-summary.json']:
 assert json.loads((out/n).read_text())==json.loads((E/n).read_text());checks[n]=True
(out/'reanalysis.json').write_text(json.dumps(dict(status='pass',new_network_conditions=0,new_radius_queries=0,source_reference='archived own-input original trajectories',source_radii='archived certified lower and failed-point upper bounds',checks=checks,selection_lock_note='The regenerated score-stage lock is bookkeeping only, not new preregistration; original locks remain immutable in the deposit.'),indent=2)+'\n')
