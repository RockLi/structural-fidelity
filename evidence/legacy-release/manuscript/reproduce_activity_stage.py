#!/usr/bin/env python3
"""Fresh reproduction of activity-selection evidence, respecting its stop gate."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    assert not out.exists() and not out.is_relative_to(ROOT);out.mkdir(parents=True);(out/'logs').mkdir()
    old=ROOT/'evidence/activity-guided-retention';new=ROOT/'evidence/budget-boundary'
    frozen={str(x.relative_to(ROOT)):sha(x) for base in [old,new] for x in base.rglob('*') if x.is_file() and not {'__pycache__','build'}.intersection(x.relative_to(base).parts)}
    def run(label,cmd):
        print('Starting '+label,flush=True)
        with (out/'logs'/f'{label}.log').open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,cwd=out)
        assert r.returncode==0,label
    # The immutable prior script writes a verification sidecar to its source.
    # Run a copied reference so that released source/evidence never changes.
    shutil.copytree(old,out/'prior-reference',ignore=shutil.ignore_patterns('__pycache__','build'))
    run('prior-retention',[sys.executable,'-B',str(out/'prior-reference/reproduce.py'),str(out/'retention')])
    old_check=json.loads((out/'prior-reference/reproduction-verification.json').read_text())
    assert old_check['status']=='pass' and old_check['scientific_state_payloads_and_count_csv_identical']==136
    run('nested-budgets',[sys.executable,'-B',str(new/'reproduce.py'),str(out/'budget')])
    new_check=json.loads((out/'budget/reproduction-verification.json').read_text());assert new_check['status']=='pass'
    gate=json.loads((out/'budget/gate.json').read_text());assert gate==json.loads((new/'gate.json').read_text())
    if not gate['proceed_migration']:
        assert not (out/'budget/run-migration-complete.json').exists()
        assert json.loads((out/'budget/migration-ledger.json').read_text())['status']=='not_run'
    for name,h in frozen.items():assert sha(ROOT/name)==h,name
    report=dict(status='pass',prior_136_conditions_reproduced=True,new_budget_reproduction=new_check,
        proceed_migration=gate['proceed_migration'],no_unapproved_migration=True,source_files_unchanged=len(frozen),
        all_new_publication_figures_must_use=dict(retention_dir=str(out/'retention'),budget_dir=str(out/'budget')))
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
