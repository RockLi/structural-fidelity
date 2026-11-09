#!/usr/bin/env python3
"""Rebuild all suites, gate claims, plot and build both preprint manuscripts.
Run using the document-authoring Python and supply --simulation-python for
NumPy/Matplotlib. A new output directory is mandatory. No archived-data fallback.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
REFERENCE_METADATA = ('figure-data.json', 'trajectory-figure-data.json')


def save(p, x):
    p.write_text(json.dumps(x, indent=2, ensure_ascii=False)+'\n')


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def frozen_inputs():
    excluded = {'__pycache__', '.mpl-cache', 'build', 'logs', 'reproduction-evidence'}
    suffixes = {'.py', '.rs', '.toml', '.json', '.csv', '.npz', '.txt', '.patch', '.conf'}
    paths = list(ROOT.glob('*.py'))+list(ROOT.glob('*.conf'))+[ROOT/n for n in REFERENCE_METADATA]
    paths += [p for p in (ROOT/'evidence').rglob('*') if p.is_file()
              and not set(p.relative_to(ROOT).parts)&excluded and p.suffix in suffixes]
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--simulation-python', default=sys.executable,
                        help='Python with NumPy and Matplotlib; current Python requires python-docx')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    assert not out.exists(), 'Use a new output directory'
    assert not out.is_relative_to(ROOT), 'Output must be outside the source package'
    # Legacy figure comparison reads these package-level metadata files. Fail
    # before creating output or spending time on simulations if packaging lost
    # a dependency; their numerical content is also frozen below.
    missing = [str(ROOT/n) for n in REFERENCE_METADATA if not (ROOT/n).is_file()]
    if missing:
        raise FileNotFoundError('Missing archived verification metadata: '+', '.join(missing))
    for name in REFERENCE_METADATA:
        assert isinstance(json.loads((ROOT/name).read_text()), dict), name
    out.mkdir(parents=True)
    (out/'logs').mkdir()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    records, inputs = [], frozen_inputs()
    save(out/'input-source-sha256.json', inputs)

    def run(stage, cmd):
        started = time.monotonic()
        log = out/'logs'/(stage+'.log')
        print('Starting '+stage, flush=True)
        with log.open('w') as stream:
            proc = subprocess.run(cmd, cwd=out, env=env, stdout=stream, stderr=subprocess.STDOUT)
        records.append(dict(stage=stage, command=cmd, returncode=proc.returncode,
                            elapsed_seconds=time.monotonic()-started, log=str(log.relative_to(out))))
        save(out/'commands.json', records)
        if proc.returncode:
            raise RuntimeError(stage+' failed: '+str(log))
        print('Passed '+stage, flush=True)

    try:
        run('earlier-experiments', [args.simulation_python, '-B', str(ROOT/'evidence/scripts/reproduce_all.py'),
                                   '--output-dir', str(out/'earlier'), '--toolchain', '1.98.1', '--skip-docx'])
        run('rewiring-experiments', [args.simulation_python, '-B', str(ROOT/'evidence/rewiring/reproduce.py'),
                                    '--output', str(out/'rewiring'), '--compare-reference'])
        run('perturbation-experiments', [args.simulation_python, '-B', str(ROOT/'reproduce_perturbation_stage.py'),
                                        '--output', str(out/'perturbation')])
        run('perturbation-report-figures', [args.simulation_python, '-B', str(ROOT/'evidence/perturbation/render_report_figures.py'),
                                           '--root', str(out/'perturbation')])
        run('sensitivity-experiments', [args.simulation_python, '-B', str(ROOT/'evidence/sensitivity/reproduce.py'),
                                       '--output', str(out/'sensitivity'), '--compare-reference'])
        sensitivity_replication = json.loads((out/'sensitivity/fresh-comparison.json').read_text())
        assert sensitivity_replication['status'] == 'pass'
        assert sensitivity_replication['scientific_conditions'] == 231
        assert sensitivity_replication['technical_sham_conditions'] == 6
        run('theory-checks', [sys.executable, '-B', str(ROOT/'verify_theory.py'),
                              '--rewiring-dir', str(out/'rewiring'), '--output', str(out/'theory-validation.json')])
        run('conditional-validation', [args.simulation_python, '-B', str(ROOT/'validate_conditional.py'),
                                       '--perturbation-dir', str(out/'perturbation'), '--rewiring-dir', str(out/'rewiring'),
                                       '--output', str(out/'conditional-validation.json')])
        run('conditional-paper-figures', [args.simulation_python, '-B', str(ROOT/'plot_conditional.py'),
                                          '--perturbation-dir', str(out/'perturbation'),
                                          '--output-dir', str(out/'conditional-figures')])
        run('sensitivity-claim-validation', [args.simulation_python, '-B', str(ROOT/'validate_sensitivity.py'),
                                             '--sensitivity-dir', str(out/'sensitivity'),
                                             '--output', str(out/'sensitivity-validation.json')])
        run('sensitivity-paper-figures', [args.simulation_python, '-B', str(ROOT/'plot_sensitivity_paper.py'),
                                         '--root', str(out/'sensitivity'),
                                         '--output-dir', str(out/'sensitivity-figures')])
        run('input-readout-posthoc-analysis', [args.simulation_python, '-B',
                                               str(ROOT/'evidence/input-readout/analyze.py'),
                                               '--sensitivity-dir', str(out/'sensitivity'),
                                               '--output-dir', str(out/'input-readout')])
        run('input-readout-independent-audit', [args.simulation_python, '-B',
                                                str(ROOT/'validate_input_readout.py'),
                                                '--sensitivity-dir', str(out/'sensitivity'),
                                                '--analysis-dir', str(out/'input-readout'),
                                                '--output', str(out/'input-readout-validation.json')])
        # Reanalysis must recover all deposited numerical tables and figures,
        # not just the handful of numbers highlighted in the manuscript.
        reference_readout = ROOT/'evidence/input-readout/analysis'
        readout_comparison = {}
        for file in sorted(reference_readout.iterdir()):
            if file.suffix not in {'.csv', '.png', '.pdf'}:
                continue
            fresh = out/'input-readout'/file.name
            assert fresh.is_file() and sha(file) == sha(fresh), file.name
            readout_comparison[file.name] = sha(fresh)
        assert len(readout_comparison) >= 15
        save(out/'input-readout-artifact-comparison.json',
             dict(status='pass', scope='All numerical CSVs and all PNG/PDF figures, exact bytes',
                  files=readout_comparison))
        run('activity-selection-experiments', [args.simulation_python, '-B', str(ROOT/'reproduce_activity_stage.py'),
                                               '--output', str(out/'activity')])
        run('activity-selection-paper-figures', [args.simulation_python, '-B', str(ROOT/'plot_activity_budget.py'),
                                                 '--retention-dir', str(out/'activity/retention'),
                                                 '--budget-dir', str(out/'activity/budget'),
                                                 '--output-dir', str(out/'activity-figures')])
        activity_comparison = {}
        for file in (ROOT/'activity-figures').iterdir():
            if file.suffix in {'.csv', '.png', '.pdf'} or file.name == 'activity-budget-figure-data.json':
                assert sha(file) == sha(out/'activity-figures'/file.name), file.name
                activity_comparison[file.name] = sha(file)
        save(out/'activity-artifact-comparison.json', dict(status='pass', files=activity_comparison))
        for language in ('en', 'zh'):
            run('build-'+language, [sys.executable, '-B', str(ROOT/'build_preprint.py'), language,
                                   '--data-dir', str(out/'earlier/tables'),
                                   '--boundary-run-dir', str(out/'earlier/execution-boundaries'),
                                   '--figures-dir', str(out/'earlier/figures'),
                                   '--rewiring-dir', str(out/'rewiring'),
                                   '--perturbation-dir', str(out/'perturbation'),
                                   '--conditional-figures-dir', str(out/'conditional-figures'),
                                   '--sensitivity-dir', str(out/'sensitivity'),
                                   '--sensitivity-figures-dir', str(out/'sensitivity-figures'),
                                   '--input-readout-dir', str(out/'input-readout'),
                                   '--activity-figures-dir', str(out/'activity-figures'),
                                   '--output-dir', str(out/'documents')])
        for name, digest in inputs.items():
            assert sha(ROOT/name) == digest, name
        report = dict(
            status='pass', completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            earlier_simulations_and_figures_fresh=True, rewiring_360_simulations_and_figures_fresh=True,
            perturbation_48_simulations_and_figures_fresh=True, archived_48_explicit_trajectories_reanalysed=True,
            sensitivity_231_simulations_and_figures_fresh=True, sensitivity_six_technical_shams_exact=True,
            archived_57_extensive_rewiring_trajectories_reanalysed=True,
            scientific_coverage=dict(new_rewiring_conditions=360, new_perturbation_conditions=48,
                                     total_new_conditions_in_these_two_suites=408,
                                     new_sensitivity_conditions=231, total_new_conditions_in_these_three_suites=639,
                                     sensitivity_technical_sham_runs_not_scientific_conditions=6,
                                     sensitivity_archived_extensive_trajectories_reanalysed_not_new_simulations=57,
                                     sensitivity_new_originals_bridged_exactly_to_archive=3,
                                     archived_explicit_trajectories_reanalysed_not_new_simulations=48,
                                     additional_earlier_experiments='E1/E3/E4/E5 and execution boundaries; see earlier validation records',
                                     perturbation_original_networks=1, perturbation_conditional_rewires=15,
                                     conditions_amplitudes_windows_and_rewires_are_not_independent_networks=True),
            eight_kernel_audits_and_300_slot_bridge_passed=True, theory_exact_checks_passed=True,
            conditional_claim_validation_passed=True, sensitivity_claim_validation_passed=True,
            sensitivity_1440_independent_metric_sets_verified=True, documents_use_fresh_outputs=True,
            input_readout_posthoc_analysis_fresh=True,
            input_readout_no_new_experimental_conditions=True,
            input_readout_independent_audit_passed=True,
            input_readout_all_csv_and_figure_bytes_reproduced=True,
            activity_selection_conditions_reproduced=True,
            activity_training_gate_respected=True,
            activity_publication_csv_figures_reproduced=True,
            source_and_reference_files_unchanged=True, frozen_input_file_count=len(inputs),
            manuscript_numerical_claims_gated_by_reference_comparison=True,
            reference_comparison_scope='Same-environment simulation states/counts remain exact; legacy perturbation derived floating CSV values use documented rtol=atol=1e-12. No cross-platform bitwise guarantee',
            docx_visual_qa='Not performed here; separate render and page inspection required',
            document_sha256={language: sha(out/'documents'/f'input-and-horizon-dependent-structural-fidelity-preprint-{language}.docx')
                             for language in ('en', 'zh')})
        save(out/'stage-validation.json', report)
        print(json.dumps(report, indent=2), flush=True)
    except Exception as exc:
        save(out/'stage-validation.json', dict(status='fail', error=str(exc), traceback=traceback.format_exc(), completed_stages=records))
        raise


if __name__ == '__main__':
    main()
