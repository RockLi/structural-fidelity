#!/usr/bin/env python3
"""Rebuild and rerun into a NEW directory using only this experiment bundle.

Optional --compare-reference checks every fresh graph, CSV and recorded state
against this delivered run. Timings are intentionally excluded from equality.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def load(p): return json.loads(p.read_text())

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',required=True,type=Path)
    p.add_argument('--compare-reference',action='store_true'); a=p.parse_args(); out=a.output.resolve()
    assert not out.exists(), 'Use a fresh output directory; nothing is overwritten'
    out.mkdir(parents=True)
    for name in ['experiment.rs','run_experiment.py','analyze.py','audit_and_diagnostics.py']:
        shutil.copy2(HERE/name,out/name)
    shutil.copytree(HERE/'frozen-inputs',out/'frozen-inputs')
    baseline=out/'.frozen-baseline'; shutil.copytree(HERE/'source',baseline/'source')
    shutil.copy2(HERE/'frozen-inputs/source-sha256.json',baseline/'source-sha256.json')
    manifest=load(baseline/'source-sha256.json')
    for name in manifest:
        replacement=HERE/'frozen-inputs/original-overrides'/name
        if replacement.exists(): shutil.copy2(replacement,baseline/'source'/name)
        assert sha(baseline/'source'/name)==manifest[name], name
    commands=[['run_experiment.py','prepare','--source',str(baseline/'source')],
              ['run_experiment.py','run'],['run_experiment.py','verify'],['analyze.py'],['audit_and_diagnostics.py']]
    for args in commands:
        if args[1:]==['run']:
            save(out/'analysis-plan-lock.json',dict(locked_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                analyze_py_sha256=sha(out/'analyze.py'),stage='before scientific runs; reproduction of the supplied analysis'))
        subprocess.run([sys.executable,'-B',str(out/args[0])]+args[1:],cwd=out,check=True)
    if a.compare_reference:
        new=load(out/'run-complete.json')['runs']; ref=load(HERE/'run-complete.json')['runs']; assert len(new)==len(ref)==360
        checked=[]
        for r in ref:
            name=r['stem']; nr=next(x for x in new if x['stem']==name)
            assert sha(out/'runs'/(name+'.csv'))==r['csv_sha256']
            with np.load(out/'runs'/(name+'.npz')) as a1,np.load(HERE/'runs'/(name+'.npz')) as a2:
                assert np.array_equal(a1['state_bits'],a2['state_bits']),name
            checked.append(name)
        for path in (HERE/'graphs').rglob('*.csv'):
            assert sha(path)==sha(out/path.relative_to(HERE))
        for name in ['run-metrics.csv','approximation-errors.csv','wiring-effects.csv','topology-error-interactions.csv','posthoc-rate-distributions.csv']:
            if name=='run-metrics.csv': continue # Contains actual timing measurements.
            assert sha(HERE/'analysis'/name)==sha(out/'analysis'/name),name
        save(out/'fresh-reproduction-comparison.json',dict(status='pass',checked_runs=len(checked),
            exact_recorded_state_payloads=True,exact_spike_and_event_csv=True,exact_graphs=True,
            exact_primary_error_csv=True,timing_equality_required=False,reference=str(HERE),
            completed_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
    print('Fresh reproduction completed:',out,flush=True)

if __name__=='__main__': main()
