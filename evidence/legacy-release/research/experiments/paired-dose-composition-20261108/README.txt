PAIRED DOSE / ERROR COMPOSITION AUDIT — 8 November 2026

Read REPORT.zh.txt for results and the recommendation on manuscript inclusion.
No manuscript was edited. No new simulation, certification or parameter run.

This analysis reads only existing count trajectories on ten random-policy chains
with all three nested budgets. It depends on:
research/experiments/score-factor-coverage-audit-20261108/dose/
output/local-circuit-preprint-20261026-final-review/evidence/activity-guided-retention/
output/local-circuit-preprint-20261026-final-review/evidence/budget-boundary/

From the repository root, use Python with NumPy and Matplotlib, e.g.:
/Users/rock/workspace/bettiai/next-brain/experiments/flywire_poc/.venv/bin/python

Recompute without overwriting outputs:
<python> -B research/experiments/paired-dose-composition-20261108/analyze.py --output-dir /tmp/new-paired-dose-audit

Verify archived outputs with independent grouping and exact arithmetic:
<python> -B research/experiments/paired-dose-composition-20261108/validate.py

Rebuild report, aggregate readout table and figures from saved results:
<python> -B research/experiments/paired-dose-composition-20261108/report.py

Scope: one original graph, one focal input, 30ms, ten nested random chains.
Replaced adjacency counts 28/56/282 correspond to 14/28/141 double-edge swaps.
All thirty trajectories are included. No slot/count zeros occur in these selected
random chains; zero reference baseline has undefined Rcount, not zero Rcount.
All L1 normalizations use the SAME original total count. Values above 100% are
possible and do not by themselves establish saturation or decorrelation.

Symmetric product decomposition separates discrepancy magnitude from retained
fraction ARITHMETICALLY, not the causal effects of edit number and edge identity.
Averaging contributions is exact; adding medians is not. Pairing does not make
these ten chains independent original networks. Readout offsets are repeated
views of the same data. No significance tests, confidence intervals, fitted
saturation curves or breakpoint estimates are asserted. Figure x axes use
actual logarithmic dose/bin widths; lines only join observed points.

Results contain 30 chain rows, 3750 node rows, 30 paired decompositions and 10890
bin/offset readouts. validation.json and reproducibility.json record independent
checks, a fresh-process byte comparison and unchanged prior bilingual manuscripts.

The compact audit bundle contains analysis code/results only. It needs the prior
evidence folders listed above and does not replace the preprint reproduction pack.
