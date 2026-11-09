Atlas heterogeneous LIF / nested horizon experiment

Start with REPORT.txt (Chinese results and interpretation), PROTOCOL.txt
(fixed design), THEORY.txt (new binary64 enclosure), FINAL-AUDIT.json
(validation status), and figures/atlas-lif-horizon-summary.png.

This directory is separate from the frozen preprint and previous experiments.
No old manuscript/package was edited. No upstream Brian2 distribution was used.
The brian2 namespace is the frontend supplied by brian2-atlas==0.2.0.

Environment
Python3.13; Apple arm64 Darwin; brian2-atlas0.2.0, native reference-f64 backend.
Exact Python/dependency versions and runner hash: environment.json.
PyPI wheel install provenance: install-report.json.
Installed source/binary hash inventory: atlas-installed-lock.json.
C replay/enclosure build:
  clang -O3 -std=c11 -fno-fast-math -ffp-contract=off -dynamiclib local.c -o local.dylib
No FMA or fast-math assumptions are substituted for the actual exported AST.

Files
  seed*/graphs/            Three copied originals and 19 legal swaps each.
  seed*/pool*.json         Inherited and fixed selected direction pools.
  events/                 Archived five input masks, mapped by model.py.
  models/                 Thirty Atlas frontend exports and full model JSONs.
  runs/                   600 compressed scientific spike trajectories;
                          all 30 originals also retain v/ge/gi end states.
  technical/              90 repeat/prefix trajectories and native run metadata.
  directions/             Reference caches, 4320 locked scores, 42834 queries,
                          radii, lower-endpoint/rational validation records.
  atlas-region-checks/     60 safe endpoints and 29 failure witnesses checked
                          with the complete Atlas network, not local replay.
  analysis/               Visibility, activity, error, coverage, stratification,
                          selection, nested radii and post-hoc floor diagnostics.
  figures/                Standalone PNG/PDF figures; no paper edits.
  preflight/              Synthetic implementation checks and all adapter fixes.
  logs/                   Batch logs, including rejected exports/errors retained.

Validation on this archived directory
  .venv/bin/python -B final_audit.py
This verifies protocol/code locks, installed package fingerprints, archived
trajectory hashes, graph invariants, reference/region checks and old package
hashes. Re-running validation does not append scientific trajectories.
MANIFEST.json seals the final archived files, excluding .venv, temporary files,
__pycache__, itself and its companion SHA file. Environment contents are covered
separately by atlas-installed-lock.json; the environment is not a portable wheel.

Reproduction sequence in a fresh sibling directory (do NOT overwrite this one)
The model/analysis modules resolve their input/output root from __file__.
Copy the root .py files, local.c, PROTOCOL.txt, protocol-lock.json, events/ and
seed*/ directories. Create empty models/, runs/, technical/, directions/,
preflight/, logs/ and tmp/ directories. Install the recorded dependency versions
in a Python3.13 .venv using pip; install brian2-atlas==0.2.0, NOT brian2.
The version-0.2.0 arm64 runner path is recorded in model.py. For other OS/Python
layouts adapt discovery explicitly and retain a new provenance lock rather than
pretending binary identity. Keep the sibling inside research/experiments/ so
prepare can check the same pre-existing frozen manuscripts/manifests.
Compile local.c as above. Then run these stages with the NEW .venv/bin/python:
  study.py prepare
  study.py networks
  scores.py
  radii.py
  validate_regions.py
  validate_atlas.py
  analyze.py network_analysis
  analyze.py direction_analysis
  posthoc_floor_audit.py
  audit_scores.py
  final_audit.py
The new preparation writes its own design/environment hashes. A repeat is a
reproduction of a now-known protocol, not a new prospective discovery run.
Final audit detects the original archive's early technical duplicate separately;
a fresh uninterrupted run has only the planned90 repeat/prefix runs. No source result is used to tune the repeat.

Plots
plot_results.py only reads saved CSV files. It requires NumPy and Matplotlib;
these can run in a separate plotting environment without importing any simulator.
The original charts were generated with the existing plotting environment,
not by installing upstream Brian2 into the Atlas simulation environment.

Interpretation constraints
- 30/100/300ms are nested prefixes, not independent repetitions.
- 100ms is not an integer number of the30ms repeated input cycles.
- A zero switch count may mean all graphs differ under BOTH inputs.
- Positive lower radius is sufficient and conservative, not a maximal safe radius.
- Twelve zero lower bounds stopped at the fixed absolute width tolerance; all
  zero-radius certificates passed. They are not proof-failure conditions.
- Agreement is conditional on disjoint brackets; report coverage and censoring.
- The reference-margin floor is fixed; its long-horizon effects were diagnosed
  post hoc and not corrected by retuning the scores.
- Native timing here is descriptive implementation cost, not a speedup claim.
