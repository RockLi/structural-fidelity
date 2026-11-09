#!/usr/bin/env python3
"""Reproduce only the completed, gated stages in a new directory."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
import numpy as np
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);p.add_argument('--report',type=Path)
    a=p.parse_args();dest=a.destination.resolve()
    assert not dest.exists();dest.mkdir(parents=True)
    design=load(ROOT/'design-lock.json')
    for rel,h in design['files'].items():
        assert sha(ROOT/rel)==h,rel
        target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
    shutil.copy2(ROOT/'design-lock.json',dest/'design-lock.json')
    for d in ['graphs','runs','technical','logs','build','analysis-train','analysis-migration']:(dest/d).mkdir(exist_ok=True)
    def cmd(*args):subprocess.run([sys.executable,*args],cwd=dest,check=True)
    cmd('audit.py','--stage','design');cmd('study.py','select')
    selection=load(ROOT/'selection-lock.json')
    for rel,h in selection['files'].items():assert sha(dest/rel)==h,rel
    shutil.copy2(ROOT/'selection-lock.json',dest/'selection-lock.json')
    cmd('audit.py','--stage','selection')
    stages=['train']
    if (ROOT/'run-migration-complete.json').exists():
        assert load(ROOT/'gate.json')['proceed_migration'] is True;stages.append('migration')
    comparisons={}
    for stage in stages:
        cmd('study.py',stage);cmd('analyze.py','--stage',stage);cmd('audit.py','--stage',stage);cmd('plot.py','--stage',stage)
        if stage=='train':assert sha(ROOT/'gate.json')==sha(dest/'gate.json'),'Gate differs in fresh reproduction'
        before=load(ROOT/f'run-{stage}-complete.json')['records'];after=load(dest/f'run-{stage}-complete.json')['records']
        assert [r['stem'] for r in before]==[r['stem'] for r in after]
        for r in before:
            stem=r['stem']
            with np.load(ROOT/'runs'/f'{stem}.npz') as x,np.load(dest/'runs'/f'{stem}.npz') as y:assert np.array_equal(x['state_bits'],y['state_bits']),stem
            assert sha(ROOT/'runs'/f'{stem}.csv')==sha(dest/'runs'/f'{stem}.csv'),stem
            x=load(ROOT/'runs'/f'{stem}.json');y=load(dest/'runs'/f'{stem}.json');x.pop('instrumented_loop_seconds');y.pop('instrumented_loop_seconds');assert x==y
        files=[]
        for x in sorted((ROOT/f'analysis-{stage}').glob('*')):
            if x.suffix in ['.csv','.json'] and 'audit' not in x.name:
                assert sha(x)==sha(dest/f'analysis-{stage}'/x.name),x.name;files.append(x.name)
        comparisons[stage]=dict(scientific_state_payloads_and_count_csv_identical=len(before),analysis_files_identical=files)
    gate=load(dest/'gate.json')
    if not gate['proceed_migration']:
        assert stages==['train'] and not (dest/'run-migration-complete.json').exists()
        assert not any(p.name.endswith(('__spatial.npz','__temporal.npz','__spatiotemporal.npz')) for p in (dest/'runs').iterdir())
    assert load(ROOT/'migration-ledger.json')==load(dest/'migration-ledger.json')
    report=dict(status='pass',fresh_directory=str(dest),regenerated_nested_candidates=1280,
        stages_reproduced=stages,all_frozen_selection_files_identical=True,gate_identical=True,
        comparisons=comparisons,migration_gate_respected=True)
    report_path=a.report.resolve() if a.report else dest/'reproduction-verification.json'
    assert not report_path.is_relative_to(ROOT),'Do not change the frozen source package when reproducing'
    report_path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
