Input controls, 2026-11-08. No manuscript changes.

Read REPORT.zh.txt, PROTOCOL.txt, protocol-lock.json, design-lock.json.
Presentation: input-controls.png/pdf. Numeric outputs: root CSVs and directions/.
All code selected before outcomes is in design-lock.json; check_integrity.py and
plot_results.py are additional post-run integrity/presentation scripts.

Environment: Apple arm64 Darwin, rustup run 1.98.1 rustc, edition2024, opt-level3.
Python3 + numpy; matplotlib for plots. Compiler/platform versions in environment.json.

From this checkout, use the experiment's scientific Python environment:
/Users/rock/workspace/bettiai/next-brain/experiments/flywire_poc/.venv/bin/python
Pass each script its absolute or cwd-relative path. The initial prepare stage is
already frozen: do not rerun network.py prepare on the archived directory.
network.py compile
network.py run --output-dir /tmp/input-control-fresh
network.py run --output-dir /tmp/input-control-repeat
For default validate.py, the two runs reside under runs/ and runs-repeat/.
directions.py score --runs-dir /tmp/input-control-fresh --output-dir /tmp/input-direction-fresh
directions.py radii --runs-dir /tmp/input-control-fresh --output-dir /tmp/input-direction-fresh
analyze_directions.py --results /tmp/input-direction-fresh
analyze_network.py, analyze_detail.py, validate.py, check_integrity.py and
plot_results.py use the archived default directories. They may safely regenerate
analysis/validation artifacts after those runs. Never overwrite scientific runs.

Dependencies are existing frozen experiment modules, imported without modification:
paired-direction-mechanism-20261108/mechanism.py and results/*;
finite-horizon-family-prototype-20261108/{prototype.py,oracle.py,kernel.c,kernel.dylib};
finite-horizon-certificate-cost-20261108/{run.py,kernel.c,kernel.dylib};
finite-horizon-certificate-audit-20261108/audit.py;
plus their archived input data paths under
output/local-circuit-preprint-20261026-final-review/evidence.
Do not treat the compact audit-bundle.zip as a standalone cross-platform package:
it contains new source and evidence, requires this checkout's frozen dependencies.
Dependency hashes are recorded in DEPENDENCIES.json; original platform libraries
must be rebuilt when changing platform. No new dependency or paper package published.

Scope: 100 graph/input conditions (60 new), 1520 direction/input conditions (912 new).
A second100-run execution is technical reproducibility, not an extra sample.
Full raw original+swap states are retained in runs/; repeated states in runs-repeat/.
The compact zip omits build binaries, repeat states, and logs; checks/results kept.
MANIFEST.json records the complete local file content (except itself/archive/caches).
