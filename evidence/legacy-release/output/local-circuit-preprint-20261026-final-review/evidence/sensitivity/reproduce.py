#!/usr/bin/env python3
"""Rebuild all local sensitivity controls in a new directory, without fallback."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess,sys
import numpy as np
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--compare-reference',action='store_true');a=p.parse_args();out=a.output.resolve()
 assert not out.exists() and not out.is_relative_to(ROOT),'Use a new directory outside this package'
 out.mkdir(parents=True)
 for name in ['study.py','analyze.py','audit.py','plot.py','reproduce.py','experiment.rs','DRIVER.txt','inherited-inputs-sha256.json']:shutil.copy2(ROOT/name,out/name)
 for name in ['source','legacy']:shutil.copytree(ROOT/name,out/name)
 for argv in [['study.py','prepare'],['study.py','run'],['study.py','verify'],['analyze.py'],['audit.py'],['plot.py']]:
  subprocess.run([sys.executable,'-B',str(out/argv[0])]+argv[1:],cwd=out,check=True)
 if a.compare_reference:
  reference=load(ROOT/'run-complete.json')['runs'];fresh=load(out/'run-complete.json')['runs'];assert len(reference)==len(fresh)==231
  for r in reference:
   stem=r['stem'];assert sha(out/'runs'/f'{stem}.csv')==r['csv_sha256']
   with np.load(ROOT/'runs'/f'{stem}.npz') as x,np.load(out/'runs'/f'{stem}.npz') as y:assert np.array_equal(x['state_bits'],y['state_bits'])
   old=load(ROOT/'runs'/f'{stem}.json');new=load(out/'runs'/f'{stem}.json')
   old.pop('instrumented_loop_seconds');new.pop('instrumented_loop_seconds');assert old==new
  for name in ['graphs','initial']:
   for f in (ROOT/name).glob('*.csv'):assert sha(f)==sha(out/name/f.name)
  compared=[]
  for f in (ROOT/'analysis').glob('*.csv'):
   assert sha(f)==sha(out/'analysis'/f.name),f.name;compared.append(f.name)
  save(out/'fresh-comparison.json',dict(status='pass',scientific_conditions=231,technical_sham_conditions=6,all_recorded_payloads_and_count_CSV_exact=True,initial_and_first_execution_metadata_exact=True,all_input_graphs_and_initial_bits_exact=True,analysis_CSV_exact=compared,timing_equality_required=False,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 print('Fresh sensitivity reproduction passed:',out)
if __name__=='__main__':main()
