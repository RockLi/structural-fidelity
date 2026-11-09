INPUT-CONDITION AND READOUT ANALYSIS (POST HOC)

No new simulations are needed for this stage. All 114 comparisons are computed
from the archived explicit trajectories in the sibling sensitivity directory.
The same 19 swaps and 19 extensive controls repeat under three input protocols.

Run from any directory, using Python with NumPy and Matplotlib installed:

  python analyze.py --sensitivity-dir ../sensitivity --output-dir NEW_DIRECTORY

The output directory must not already contain files. The checked-in result is
analysis/. The parent reproduction entrypoint also calls this command on its
fresh sensitivity output directory, then audits the resulting tables/figures.

analysis-plan.json states what was known before this reanalysis and fixes all
conditions, widths, offsets, smoothing constants, formulas, and limits. It is
explicitly a post-hoc plan, not preregistration or independent confirmation.
It must not be retrospectively relabeled as a prospective protocol.

Main outputs:
* input-switching.csv: all 57 swaps/input outcomes.
* graph-input-patterns.csv: same-graph input switching, 19 rows.
* error-composition.csv: exact integer temporal-first decomposition, 114 rows.
* binning-values.csv: every width/offset/readout for every comparison.
* binning-separation.csv: full range separation at each width/readout,
  including the stricter cross-offset envelope comparison.
* smooth-values.csv: full-tail exponential distance, 570 rows.
* summary.json and METHODS-RESULTS.txt: definitions, numerical summaries, limits.
* three PNG/PDF figure pairs: input-switching, error-composition,
  binning-robustness.
* input-sha256.json: fingerprints of every archived input and both analysis
  source files; no host-dependent absolute paths are required.
* validation.json: exact identities, analytic distance tests, input immutability
  and hashes of generated outputs. The root package manifest locks this file.

The smooth score is normalized squared van Rossum distance, not an L1 error
percentage. The 1089 common-offset comparisons are repeated measurements of
the same archived data, not 1089 independent experiments. The composition is
temporal-first, order-dependent and does not identify moved-spike distances.

Plotting produces no timestamp-dependent PDF metadata. Numerical and figure
outputs are deterministic for the recorded software environment. A fresh
analysis writes a new output directory; it never modifies the old evidence.
