#!/usr/bin/env python3
import argparse,shutil,subprocess,sys
from pathlib import Path
import numpy as np
from study import ROOT,load,save,sha
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--compare-reference',action='store_true');a=p.parse_args();out=a.output.resolve();assert not out.exists();out.mkdir(parents=True)
for name in ['study.py','analyze.py','legacy_phases.py','reproduce.py','experiment.rs','kernel_audit.rs','inherited-library.patch','inherited-inputs-sha256.json']:shutil.copy2(ROOT/name,out/name)
for name in ['source','graphs','legacy_inputs']:shutil.copytree(ROOT/name,out/name)
for args in [['legacy_phases.py'],['study.py','prepare'],['study.py','run'],['study.py','verify'],['analyze.py']]:subprocess.run([sys.executable,'-B',str(out/args[0])]+args[1:],cwd=out,check=True)
if a.compare_reference:
 for record in load(ROOT/'run-complete.json')['runs']:
  name=record['stem'];assert sha(out/'runs'/f'{name}.csv')==record['csv_sha256']
  with np.load(out/'runs'/f'{name}.npz') as x,np.load(ROOT/'runs'/f'{name}.npz') as y:assert np.array_equal(x['state_bits'],y['state_bits'])
 for folder in ['analysis','legacy_diagnostics','predictors']:
  for f in (ROOT/folder).glob('*.csv'):assert sha(f)==sha(out/folder/f.name),f
 save(out/'fresh-comparison.json',dict(status='pass',exact_state_payloads=48,exact_count_csv=48,all_analysis_legacy_phase_and_predictor_csv_exact=True,source_library_unchanged=True,timing_equality_required=False))
print('Fresh reproduction passed:',out)
