#!/usr/bin/env python3
"""Rebuild frozen Rust sources in an isolated directory. No Cargo downloads required."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, tempfile, time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mode', choices=['original', 'original_instrumented', 'raw_sum', 'kappa_only'], default='original')
parser.add_argument('--stage', choices=['complete', 'initial'], default='complete', help='initial kappa_only retains the historical failing PSD assertion')
parser.add_argument('--work-dir', type=Path, help='New or empty isolated output directory; defaults to a new temporary directory')
parser.add_argument('--toolchain', default='1.98.1', help='Explicit rustup toolchain; default matches manuscript validation')
parser.add_argument('--rustc', help='Override with a specific compiler executable instead of rustup selection')
args = parser.parse_args()
compiler = [args.rustc] if args.rustc else ['rustup', 'run', args.toolchain, 'rustc']
compiler_version = subprocess.check_output(compiler + ['--version', '--verbose'], text=True)
evidence = Path(__file__).resolve().parents[1]
source = evidence / 'original' / 'source'
manifest = json.loads((evidence / 'original' / 'source-sha256.json').read_text())
for name, expected in manifest.items():
    actual = hashlib.sha256((source / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f'Source hash mismatch: {name}')
work = args.work_dir or Path(tempfile.mkdtemp(prefix='local-circuit-reproduce-'))
if work.exists() and any(work.iterdir()):
    raise SystemExit('The output directory must be empty to preserve earlier results.')
work.mkdir(parents=True, exist_ok=True)
(work / 'compiler-provenance.json').write_text(json.dumps({'compiler_command': compiler, 'version_verbose': compiler_version}, indent=2) + '\n')
shutil.copytree(source, work, dirs_exist_ok=True)
for name in ['bin', 'logs', 'docs/phase3']:
    (work / name).mkdir(parents=True, exist_ok=True)
if args.mode != 'original':
    filename = 'diagnostic-complete.patch' if args.stage == 'complete' else 'diagnostic.patch'
    patch = evidence / 'diagnostics' / args.mode / 'patches' / filename
    if not patch.exists():
        raise SystemExit(f'No {args.stage} patch for {args.mode}')
    subprocess.run(['patch', '-p1', '-i', str(patch)], cwd=work, check=True)
commands = [('build-library', compiler + ['--edition=2024', '-C', 'opt-level=3', '--crate-name', 'next_brain', '--crate-type', 'lib', 'src/lib.rs', '-o', 'bin/libnext_brain.rlib'])]
if args.mode == 'original':
    commands += [('build-lib-tests', compiler + ['--edition=2024', '-C', 'opt-level=3', '--crate-name', 'next_brain', '--test', 'src/lib.rs', '-o', 'bin/lib_tests']), ('lib-tests', ['bin/lib_tests', '--nocapture', '--test-threads=1'])]
    targets = ['phase1_fidelity', 'phase2_connectivity', 'phase2_lpu', 'phase2_examples', 'stage14_api', 'phase3_benchmarks']
else:
    targets = ['phase3_benchmarks']
for target in targets:
    commands.append(('build-' + target, compiler + ['--edition=2024', '-C', 'opt-level=3', '--test', 'tests/' + target + '.rs', '--extern', 'next_brain=bin/libnext_brain.rlib', '-o', 'bin/' + target]))
    command = ['bin/' + target]
    if args.mode != 'original':
        command.append('bench_stateful_proxy_closure_and_psd')
    commands.append((target, command + ['--nocapture', '--test-threads=1']))
results = []
for name, command in commands:
    start = time.monotonic()
    with (work / 'logs' / (name + '.log')).open('w') as log:
        log.write('$ ' + ' '.join(command) + '\n')
        log.flush()
        result = subprocess.run(command, cwd=work, stdout=log, stderr=subprocess.STDOUT)
    record = {'stage': name, 'command': command, 'returncode': result.returncode, 'elapsed_s': time.monotonic() - start}
    results.append(record)
    print(json.dumps(record), flush=True)
    (work / 'run-results.json').write_text(json.dumps(results, indent=2) + '\n')
    if result.returncode:
        print(f'Run stopped; inspect {work / "logs" / (name + ".log")}')
        raise SystemExit(result.returncode)
print(f'Reproduction complete. Outputs: {work}')
