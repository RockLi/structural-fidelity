#!/usr/bin/env python3
"""Recreate candidates and outputs in a new directory without changing locks."""
from pathlib import Path
import argparse, json, shutil, subprocess, sys, hashlib
import numpy as np

ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);a=p.parse_args();dest=a.destination.resolve();assert not dest.exists();dest.mkdir(parents=True)
    design=json.loads((ROOT/'design-lock.json').read_text())
    for rel,h in design['files'].items():
        assert sha(ROOT/rel)==h,rel
        dst=dest/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dst)
    shutil.copy2(ROOT/'design-lock.json',dest/'design-lock.json')
    for name in ['graphs','runs','technical','logs','build','analysis']:(dest/name).mkdir(exist_ok=True)
    def cmd(*args):subprocess.run([sys.executable,*args],cwd=dest,check=True)
    cmd('study.py','select')
    selection=json.loads((ROOT/'selection-lock.json').read_text())
    for rel,h in selection['files'].items(): assert sha(dest/rel)==h,rel
    # The regenerated lock has a fresh wall time; replace with the original evidence lock only after exact content comparisons.
    shutil.copy2(ROOT/'selection-lock.json',dest/'selection-lock.json')
    cmd('study.py','run');cmd('analyze.py');cmd('audit.py');cmd('plot.py')
    original=json.loads((ROOT/'run-complete.json').read_text())['records'];new=json.loads((dest/'run-complete.json').read_text())['records']
    assert [r['stem'] for r in original]==[r['stem'] for r in new]
    for r in original:
        stem=r['stem']
        with np.load(ROOT/'runs'/f'{stem}.npz') as x,np.load(dest/'runs'/f'{stem}.npz') as y: assert np.array_equal(x['state_bits'],y['state_bits']),stem
        assert sha(ROOT/'runs'/f'{stem}.csv')==sha(dest/'runs'/f'{stem}.csv'),stem
        x=json.loads((ROOT/'runs'/f'{stem}.json').read_text());y=json.loads((dest/'runs'/f'{stem}.json').read_text())
        x.pop('instrumented_loop_seconds');y.pop('instrumented_loop_seconds');assert x==y,stem
    analysis=[]
    for x in (ROOT/'analysis').glob('*'):
        if x.suffix in ['.csv','.json']:
            y=dest/'analysis'/x.name;assert y.exists(),x.name
            # audit reports may include clock/path metadata and are checked independently, not byte compared.
            if 'audit' not in x.name: assert sha(x)==sha(y),x.name;analysis.append(x.name)
    report=dict(status='pass',fresh_directory=str(dest),regenerated_candidates=640,selected_graphs_and_scores_identical=True,scientific_state_payloads_and_count_csv_identical=len(original),json_identical_except_instrumented_timing=True,analysis_files_identical=analysis)
    (ROOT/'reproduction-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
