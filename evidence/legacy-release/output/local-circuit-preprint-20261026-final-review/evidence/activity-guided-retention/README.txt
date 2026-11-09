ACTIVITY-GUIDED STRUCTURAL RETENTION — LOCKED FOLLOW-UP, 2026-10-25

Start with RESULTS.zh.html (self-contained Chinese report) or RESULTS.zh.txt.
This module is complete; the existing English/Chinese preprint was not edited.
This is a prospective exploratory follow-up to prior inspected experiments,
not a public preregistration and not a new independent original-network sample.

QUESTION AND SCOPE
On the existing 125-chunk homogeneous seed-99 network, does selecting a graph
to reduce reference-activity input mismatch improve closed-loop fidelity on
the training and fixed held-out inputs? All 2,845 edges remain. Exactly 282
original adjacency pairs are replaced in every candidate. The matched budget
is structural, not a claim about matched computation, speed or compression.
Ten candidate banks contain 64 graphs each. Four rules select from each bank.
Thirty-three unique selected graphs plus the original are simulated on four
inputs: 136 scientific conditions, 160 selector-input rows, one technical
repeat. Reproduction repeats the same conditions, not new scientific samples.

MAIN RESULT
Training coactivity score was lower than random in all ten banks (paired
relative reduction mean 19.33%), but normalized raw-slot identified L1 rose:
training +0.09255; mean across three held-out inputs +0.12787 (8/10 worse).
Coactivity did not improve the locked main endpoint over mean or shuffled
controls either. Split-pulse-only input had better coarse secondary metrics,
but worse raw-slot error. Report all inputs and metrics without swapping the
primary endpoint. This is conditional evidence of an objective mismatch,
not a general impossibility result for activity-guided structure selection.

CONTENTS
protocol.json                 Fixed rules, seeds, budget, inputs and endpoints
design-lock.json               Code/data/design SHA256 before new simulations
selection-lock.json            Candidate/score/selection SHA256 before runs
inherited/                    Original graph and archived training trajectory
source/                       Frozen original Rust library (55 files)
experiment.rs, DRIVER.txt      External event CSV driver and execution semantics
events/                       Fixed input event tables, equal external dose
graphs/                       Original and all 640 candidate graphs
candidates.csv                All 2,560 candidate scores, not only winners
selection.json                Forty selector memberships, including overlaps
graph-aliases.json             Identical graph byte aliases
planned-runs.json              Unique graph-input simulation plan
runs/                         Raw count CSV, uint32 state NPZ, run metadata
technical/                    One repeated training reference run
analysis/                     Numerical tables, definitions, validation, figures
audit*.json / *-audit.json     Independent and stage-specific audit evidence
reproduction-verification.json  Full fresh-directory reproduction comparison
RESULTS.zh.*, report-data.json  Post-outcome interpretation, not selection input
PACKAGE-SHA256.json            Delivery manifest (all packaged files except self)

SOFTWARE
Reference platform: Apple arm64 Darwin.
Rust: rustc 1.98.1, --edition=2024 -C opt-level=3; exact version in environment.json.
Python: 3.13.5, NumPy 2.5.4, Matplotlib 3.10.8.
The library and experiment compile directly with rustc; no Cargo downloads.
Source activity and metric calculations use NumPy float64, simulation f32.
No timing in this package is a performance benchmark.

FULL REPRODUCTION (destination must not exist)
Unpack the archive, enter its top-level experiment folder, and use a Python
environment with the above scientific packages and rustup toolchain installed:

  python reproduce.py /absolute/path/to/new-empty-study-directory

The script verifies and copies the design-locked inputs, regenerates every
candidate/score/selection, byte-compares their files, rebuilds the Rust driver,
reruns all unique selected conditions and the technical repeat, reruns analysis
and independent audit, and redraws figures. It checks recorded state payloads,
count CSV and numerical outputs exactly. Metadata agree except instrumented
wall time; archive container hashes are provenance, not the scientific equality
criterion. Fresh run timestamps are retained. The original selection lock is
copied into the new directory only after regenerated selection files match it.
reproduction-verification.json in the source folder is refreshed by this command.

READ-ONLY AUDIT OF DELIVERED EVIDENCE
  python audit.py --output /absolute/path/to/audit-report.json
An audit checks artifact consistency; timestamps alone cannot prove historical
non-access. During this study selection was completed before any new simulation.

RE-ANALYSIS / FIGURES WITHOUT RE-SIMULATION
  python analyze.py --output-dir /absolute/path/to/new-analysis
  python plot.py --analysis-dir /absolute/path/to/new-analysis
The output locations must be empty. Do not overwrite the frozen evidence.
python report.py regenerates only the post-outcome presentation from numerical
results; it was written after outcomes and is not a design-locked analysis.

METRICS AND LIMITS
Primary: sum_{t,k}|s_candidate-s_original| / sum_{t,k}s_original for each input.
Within a bank average the three held-out values equally; then compare selectors
in the same bank. All ten paired values and full ranges are provided. Ratios
can exceed one; they are not error probabilities. Coactivity scores use
representative counts (raw chunk counts/100), separate E/I channels and 298
source slots whose recurrent arrivals lie inside the 300-slot window.
The score depends on zero-lag second moments and is invariant to a common
time permutation. Per-source independent shuffling changes coactivity while
preserving each source count distribution. It is not a test of event order.
The four coarse/state metrics that improve on split pulses are dependent
observations from the same runs. No p-values or population CIs are claimed.
The inherited simplified kernel uses uncalibrated voltage coordinates and
unchanged dormant/refractory update rules; this is not a standard biophysical
model validation. Each chunk's 100 units remain exact synchronized copies.
No evidence here establishes an optimal geometry, proxy memory benefit,
biological fidelity, compression, or universal failure of activity guidance.

INHERITED PROVENANCE
Copied without changes from the prior package:
output/local-circuit-preprint-20261024-input-readout/evidence/sensitivity/
Source library, original seed-99 graph, and archived homogeneous original
focal_burst explicit trajectory. The complete 300x125x10 field payload and
count CSV for the new original train run match that archive exactly.
