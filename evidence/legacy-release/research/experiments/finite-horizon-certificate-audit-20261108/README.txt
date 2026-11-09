Finite-horizon nonzero-perturbation feasibility audit — 2026-11-08

Read REPORT.zh.txt for findings and THEORY.txt for the condition and proof.
This folder contains an audit, not an updated preprint or a new simulation suite.
It requires the unchanged release at:
  output/local-circuit-preprint-20261026-final-review/
relative to the repository root. No full network simulator is invoked.

Files:
  protocol.json             Post-hoc scope, predeclared guard and stopping rules
  audit.py                  Reference-only rational interval certificate
  check_and_cost.py         Arithmetic checks, archive hashes, local cost checks
  target-17-cases.csv        All requested cases, including the noncertificate
  results/cases.csv         All 57 archived single-swap/input cases
  results/summary.json      Counts, setup work, source environment
  results/input-sha256.json Exact source evidence used
  checks/costs.csv          Per-case timing; historical Rust times labeled separately
  checks/summary.json       Arithmetic, integrity and scheduling diagnostics
  reproducibility.json     Fresh-directory repeat of all nontiming case fields

Use Python 3.13 with NumPy. No scientific plotting/document packages are needed.
From the repository root, choose output directories that do not exist:
  python3 -B research/experiments/finite-horizon-certificate-audit-20261108/audit.py --output-dir /tmp/certificate-audit-new
  python3 -B research/experiments/finite-horizon-certificate-audit-20261108/check_and_cost.py --output-dir /tmp/certificate-checks-new

Current recorded runtime:
 /Users/rock/workspace/bettiai/next-brain/experiments/flywire_poc/.venv/bin/python

No confidence intervals, transfer claims or runtime speedup claims are supported.
Results are computational guarantees under the stated finite-precision execution
contract, accompanied by empirical implementation checks; not proof-assistant
verification. The prospective selection/migration protocol remains stopped.
