POST HOC SCORE-FACTOR / COVERAGE / DOSE-AVAILABILITY AUDIT
8 November 2026

This folder contains offline analyses only. No new simulation, point replay,
certificate query, radius refinement or manuscript edit was performed.
Read REPORT.zh.txt first. analysis-summary.png/pdf summarize the evidence.

DEPENDENCIES
Use Python with NumPy (Matplotlib for plotting), e.g. the scientific interpreter:
/Users/rock/workspace/bettiai/next-brain/experiments/flywire_poc/.venv/bin/python

Keep this folder at research/experiments/score-factor-coverage-audit-20261108.
It reads the existing paired-direction-mechanism-20261108 result CSVs and pool,
finite-horizon-certificate-audit-20261108/audit.py for reconstruction of archived
reference states, and output/local-circuit-preprint-20261026-final-review/evidence
for original references and the activity-guided-retention/budget-boundary data.
It does not load or invoke native certificate libraries. Archived source files
and all consumed inputs are SHA256 recorded in results/ and dose/.
The compact audit ZIP contains this analysis, not copies of the prior evidence.
It is NOT a standalone replacement for the existing preprint reproduction pack.

RECOMPUTE WITHOUT OVERWRITING DEPOSITED RESULTS
Run from the repository root, with <python> replaced by the interpreter above:
<python> -B research/experiments/score-factor-coverage-audit-20261108/analyze_scores.py --output-dir /tmp/new-score-audit
<python> -B research/experiments/score-factor-coverage-audit-20261108/audit_dose.py --output-dir /tmp/new-dose-audit
Output directories must not already exist. Compare CSVs and summary.json with
results/ and dose/. Environment metadata records the current runtime.

VERIFY DEPOSITED RESULTS
<python> -B research/experiments/score-factor-coverage-audit-20261108/validate.py
This independently recomputes pair orders, credits, completion bounds and ratio
checks; it also checks matrix/convolution score calculations and input hashes.
It writes validation.json and the post-result exact-tie diagnostic.

REBUILD FIGURE / REPORT
<python> -B research/experiments/score-factor-coverage-audit-20261108/plot_summary.py
<python> -B research/experiments/score-factor-coverage-audit-20261108/write_report.py

INTERPRETATION
Factorial scores use the same eligible-slot mask; legacy_raw retains the old
all-slot definition separately. Original mean and shuffle controls ALREADY use
both the temporal filter and reference threshold margins. No control is silently
redefined. All comparisons use identical resolved sets and report target-level
macro and direction-level micro summaries separately. Methods were not tuned
against new outcomes. This is nevertheless post hoc, not independent validation.

Unknown radius upper bounds are infinity, not the certification cap. Separation
bins use L_safer/U_less_safe, a guaranteed LOWER bound on the actual ratio, not an
exact radius ratio. Unresolved score-completion ranges are loose logical ranges,
not confidence intervals; hypothetical independent completions need not form a
single globally realizable ranking. Predicted ties receive half credit throughout.
No p-values are assigned to dependent direction pairs.

The dose audit checks all 1,920 graph prefixes and 90 completed training variants,
with graph identities and actual NPZ/CSV/JSON hashes. Ten complete three-budget
chains exist, all selected by the original random policy. Earlier single-swap
controls share the focal input, but not these chains. No R_count dose calculation
was performed. Counts 28/56/282 refer to replaced original adjacencies, not swaps.
