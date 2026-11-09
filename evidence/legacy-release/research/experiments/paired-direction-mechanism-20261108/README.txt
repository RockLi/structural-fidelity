Paired direction/input mechanism audit — incremental reproduction package

Read REPORT.zh.txt; protocol was frozen before the first new-direction trial.
The primary graph is ALWAYS the original archived125-chunk graph. Old swaps
supply only target-pair identities. No new full-network simulations or paper edits.

Requirements: Python3 + NumPy; Matplotlib only for plotting. Reuses the existing
family prototype's C library and original audit helpers. Keep this directory at
research/experiments/paired-direction-mechanism-20261108 in the same repository,
alongside prior finite-horizon audit/cost/family directories and
output/local-circuit-preprint-20261026-final-review. The large source evidence
corpus is not duplicated here. Absolute source hashes refer to the original
checkout; relocating/rebuilding requires regenerating provenance.

From this directory with the scientific Python environment active:
python -B mechanism.py --output-dir /tmp/paired-fresh1
python -B mechanism.py --output-dir /tmp/paired-fresh2
python -B analyze.py --results /tmp/paired-fresh1
python -B analyze.py --results /tmp/paired-fresh2

Run folders must not exist. To reproduce every included artifact, use a fresh
copy of this directory and move aside results/,repeat/ and generated reports;
run the commands with results and repeat as output names, then:
python -B validate.py
python -B verify.py
python -B plot_results.py
python -B window_audit.py

validate.py reads results/, rechecks all lower bounds/endpoints, selection locks,
budget invariants and25 exact-rational conditions (takes several minutes).
verify.py compares results/ and repeat/ plus original audit/preprint manifests.
plot_results.py writes mechanism-summary.png and reversal-examples.json.
No runtime comparison is claimed in this audit. The validation and repeat jobs
may overlap; their recorded setup times are not controlled benchmarks.

Implementation
mechanism.py: pool construction and source-only scores locked before outcomes;
parameter-family certification; independent target-by-target native point replay;
finite radius bracketing; exact entry/Python witness validation.
Uses prototype.py/kernel.dylib in the previous family prototype unchanged.
analyze.py: interval-resolved ranks, reversal counts, frozen/conditioned scoring,
selection wins/losses/ties/unresolved, first-failure predictions.
validate.py: endpoint containment, rational enclosures, budget/selection checks.
verify.py: repeat and original evidence integrity.
window_audit.py: explicitly POST-HOC score-only sensitivity check; preserves
source counts within the first298 emission slots that arrive in the300-slot
window. Recomputes mean/shuffle scores and tonic control selections against
existing radius brackets; no new perturbation runs or replacement of locked
primary results. Outputs window-score-sensitivity.csv,
window-selection-sensitivity.csv and window-sensitivity.json.

Data tables in each run
pool-lock.json:19 target pairs,16 fixed sign vectors, grouped edge metadata.
scores.csv: reference-informed temporal/mean/shuffle/raw/full scores and activity.
selection-lock.csv/json: tonic-only selections, score/pool digests. The flag
perturbed_results_seen=False denotes the selection phase of this process, not
that historical reference data or earlier audit outcomes were never seen.
radii.csv: certified lower L, point-witness upper U, stopping reason and witness.
queries.csv: every initial/refinement query including proof gaps.
rank-concordance.csv: per-target-pair descriptive metrics; overlapping intervals
are not ordered. Random ranking uses the fixed random candidate-pool order.
selection-transfer.csv: paired selection outcomes and radius-ratio bounds;
tie_same_direction and tie_at_cap are distinct from unresolved overlap.
input-reversals.csv: resolved paired order changes across inputs.
conditioned-vs-frozen.csv: no new selection; compares reference-specific scores.
failure-predictions.csv: actual earliest affected-target guard vs score bottleneck.
analysis.json: descriptive summaries, no independent-sample significance claims.

Important semantics
A radius certifies the whole symmetric parameter interval, not just its endpoints.
An actual failed point supplies U; failure of the enclosure alone does not.
Midpoint endpoints passing without a whole-interval certificate leaves a gap.
A capped radius is censored, not an exact maximum. First failures are selected
by time across BOTH targets, unlike the old target-major return order.
The inherited label threshold-inconclusive in point-witness CSV rows actually
means a concrete threshold decision mismatch; in certificate rows it means an
unresolved enclosure. No claims of divergence rely on the latter alone.

Same-budget comparisons are between directions: group weight multisets match
at common t, but are not identical to the unperturbed graph's weight multiset.
Temporal scoring uses the full unperturbed reference window and original margins;
it is not an online forecast of an unseen input. Full sensitivity is an algebraic
ceiling closely tied to the certificate, not an independent learned predictor.
The time-shuffled activity is only a scoring control, not a realizable new
closed-loop input. All results concern one graph and correlated target pairs.
