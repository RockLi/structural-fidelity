#!/usr/bin/env python3
"""Reproduce this revision from deposited trajectories, without new simulations.

Use the document Python and supply --simulation-python with NumPy/Matplotlib.
For a complete simulator-to-document rerun use reproduce_stage.py instead.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--simulation-python', default=sys.executable)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    assert not out.exists() and not out.is_relative_to(ROOT), 'Use a new directory outside this package'
    out.mkdir(parents=True)
    (out/'logs').mkdir()
    commands = []
    def run(name, command):
        print('Starting ' + name, flush=True)
        with (out/'logs'/(name+'.log')).open('w') as stream:
            result = subprocess.run(command, cwd=out, stdout=stream, stderr=subprocess.STDOUT,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        commands.append(dict(stage=name, command=command, returncode=result.returncode))
        save(out/'commands.json', commands)
        assert result.returncode == 0, name
    source = ROOT/'evidence/sensitivity'
    run('posthoc-analysis', [args.simulation_python, '-B', str(ROOT/'evidence/input-readout/analyze.py'),
                            '--sensitivity-dir', str(source), '--output-dir', str(out/'input-readout')])
    run('independent-audit', [args.simulation_python, '-B', str(ROOT/'validate_input_readout.py'),
                             '--sensitivity-dir', str(source), '--analysis-dir', str(out/'input-readout'),
                             '--output', str(out/'independent-audit.json')])
    compared = {}
    for file in sorted((ROOT/'evidence/input-readout/analysis').iterdir()):
        if file.suffix in {'.csv', '.png', '.pdf'}:
            fresh = out/'input-readout'/file.name
            assert fresh.is_file() and digest(file) == digest(fresh), file.name
            compared[file.name] = digest(fresh)
    run('activity-training-analysis', [args.simulation_python, '-B', str(ROOT/'evidence/budget-boundary/analyze.py'),
                                      '--stage', 'train', '--output-dir', str(out/'budget-analysis-train')])
    for file in (ROOT/'evidence/budget-boundary/analysis-train').iterdir():
        if file.suffix in {'.csv', '.json'} and 'audit' not in file.name:
            assert digest(file) == digest(out/'budget-analysis-train'/file.name), file.name
    run('activity-independent-audit', [args.simulation_python, '-B', str(ROOT/'evidence/budget-boundary/audit.py'),
                                       '--stage', 'train', '--output', str(out/'activity-independent-audit.json')])
    # Create a presentation-only view of the newly analyzed tables; graph/run
    # evidence stays in the deposited module and is separately audited above.
    view=out/'budget-view';view.mkdir();(view/'analysis-train').symlink_to(out/'budget-analysis-train',target_is_directory=True)
    for name in ('protocol.json','gate.json'):
        (view/name).write_bytes((ROOT/'evidence/budget-boundary'/name).read_bytes())
    run('activity-paper-figures', [args.simulation_python, '-B', str(ROOT/'plot_activity_budget.py'),
                                  '--retention-dir', str(ROOT/'evidence/activity-guided-retention'),
                                  '--budget-dir', str(view), '--output-dir', str(out/'activity-figures')])
    for file in (ROOT/'activity-figures').iterdir():
        if file.suffix in {'.csv','.png','.pdf'} or file.name=='activity-budget-figure-data.json':
            assert digest(file)==digest(out/'activity-figures'/file.name),file.name
            compared['activity/'+file.name]=digest(file)
    for language in ('en', 'zh'):
        run('build-'+language, [sys.executable, '-B', str(ROOT/'build_preprint.py'), language,
                               '--input-readout-dir', str(out/'input-readout'),
                               '--activity-figures-dir', str(out/'activity-figures'),
                               '--output-dir', str(out/'documents')])
    save(out/'validation.json', dict(status='pass', new_simulations=0,
         scope='Deposited trajectories to fresh post-hoc CSVs, figures and bilingual DOCX. Earlier evidence retained.',
         compared_artifacts=compared, independent_audit=True,
         activity_training_reanalysis=True,activity_gate_preserved=True,
         document_visual_qa='Separate render and inspection required'))
    print('Passed archived-data reanalysis and bilingual document rebuild.', flush=True)


if __name__ == '__main__':
    main()
