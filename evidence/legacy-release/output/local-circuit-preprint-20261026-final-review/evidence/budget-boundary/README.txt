NESTED SMALL-BUDGET ACTIVITY-GUIDED STRUCTURE SELECTION — 2026-10-26

This is a prospective gated follow-up motivated by the inspected negative
9.91% experiment. It reuses the same original graph, candidate proposal seeds,
source training activity, and known test inputs. It is not a public
preregistration, fresh network cohort, or new independent held-out sample.

QUESTION
At approximately 1% and 2% adjacency changes, does a frozen-source coactivity
score select graphs with consistently better CLOSED-LOOP training fidelity
than random selection? Only if both budgets pass the fixed training gate is
conditional transfer to the three prior-known inputs authorized.

BUDGETS AND PAIRING
All 2,845 edges remain. The original-adjacency replacement counts by
EE/EI/IE/II arm are [14,6,6,2] (28 total, 0.98418%) and [30,12,12,2]
(56 total, 1.96837%). Formula: 2*max(1,floor(M_arm*f/2+0.5)). Each arm rounds
to the nearest even count, half upward, with minimum two changed directed
adjacencies (one accepted two-edge swap). The II
budgets therefore coincide; actual per-arm fractions are not all 1% or 2%.

For each of the old 640 candidate seeds, the complete OLD 9.91% proposal
sequence is regenerated and its final graph SHA256 checked against the prior
archive. Smaller graphs take prefixes WITHIN EACH ARM of that full sequence.
The shared RNG is not prematurely stopped between arms. All candidate and
selector memberships are retained, including identical graphs and ties.
Ten blocks x 64 candidates x two nested budgets = 1,280 candidate graphs;
four selectors per block/budget = 80 policy memberships. Original source rows,
per-node per-arm degrees, strengths, weight multisets, and delays are exact.
This is matched structural change, not pruning, edge compression or speedup.

SELECTION AND INPUTS
Random, mean, coactivity, and independently time-shuffled source controls use
exactly the old score definitions and seeds. Coactivity is an uncentered
zero-lag second-moment score, invariant under common time permutation; it is
not event order or a learned memory. All scores use only archived original
focal-burst training activity at source slots 0..297. No old held-out state
file is copied or read. The source library and external event driver are
unchanged. Each chunk still contains 100 identical synchronized units.
For the smaller budgets, direct=DeltaW@S is evaluated in promoted float64;
J_coactivity=sum(direct^2), J_mean=sum((sum_time direct)^2)/298. These are the
same mathematical scores, evaluated to preserve exact zero residuals. Exact
numeric minima and candidate-index ties are used without score tolerances.
The historical 9.91% score tables and selections are not changed.

TRAINING GATE (FIXED BEFORE ANY NEW SIMULATION)
For EACH budget, coactivity-minus-random normalized raw-slot identified L1
must have mean < -1e-12, median < -1e-12, and at least seven strict wins out
of ten matched blocks. Both budgets must pass. Extra comparator guards require
coactivity-minus-mean and coactivity-minus-shuffled each to have mean <= 1e-12
and wins >= losses. Ten defined pairs are required throughout. Ties are not
wins. Zero reference total counts produce null ratios and fail the gate.
These are pragmatic continuation rules, not significance or formal
noninferiority tests. The extra guards can pass with all ties; they do not
establish a coactivity-specific effect. Nested budgets are not independent
replications. A failed gate stops ALL migration simulations and creates an
explicit not_run ledger. Do not reinterpret secondary metrics as gate success.

CONDITIONAL MIGRATION
Only if the joint training gate passes AND independent audit validates the
exact gate and its input hashes, run the same selected graphs on the old
spatial, temporal, and spatiotemporal event CSV protocols. These conditions
were previously known; no masks or pulses are newly selected. The migration
primary endpoint is the equal-weight average of all three normalized raw-slot
losses within each block/budget. Every individual input must also be shown.

EXECUTION ORDER (Python with NumPy/Matplotlib, rustup toolchain 1.98.1)
Do not execute prepare until protocol and independent audit have been reviewed.
  python study.py prepare
  python audit.py --stage design
  python study.py select
  python audit.py --stage selection
  python study.py train
  python analyze.py --stage train
  python audit.py --stage train
  python plot.py --stage train
Only when gate.json proceed_migration is true:
  python study.py migration
  python analyze.py --stage migration
  python audit.py --stage migration
  python plot.py --stage migration

FULL REPRODUCTION
  python reproduce.py /absolute/path/to/new-empty-study-directory
The script regenerates all candidate prefixes and selections, compares locked
files, rebuilds the frozen library/driver, and reruns only completed authorized
stages. State payloads and count CSV are exact; instrumented wall time and
archive container hashes are provenance rather than scientific equality.
Derived numerical CSV/JSON are byte-compared. Audit/provenance timestamps are
excluded. A failed training gate cannot trigger migration during reproduction.
The verification report is written in the fresh destination (or --report
outside the source package); reproduction never changes the source package.

OUTPUTS
protocol.json, design-lock.json: fixed design/code/source/event hashes.
candidates.csv, selection.json, selection-lock.json: all scores/memberships.
prefix-sequences.json: full accepted-swap sequences and archived full hashes.
graph-aliases.json: canonical identical graph bytes across the candidate bank.
planned-train.json, planned-migration.json: conditional stage plans.
run-train-complete.json, run-migration-complete.json: completed-stage records.
analysis-train/, analysis-migration/: metrics, definitions, figures, validation.
gate.json: observed paired effects, every Boolean criterion, joint decision.
migration-ledger.json: not_run / authorized_pending / completed with reason.
audit-*.json: independent stage checks and hashes of audited input files.
reproduction-verification.json: fresh-directory scientific equality checks.

SECONDARY METRICS AND LIMITS
1-ms identified L1; cumulative identified L1; Dcount/Dslot (null for Dslot=0);
full-tail exponential van Rossum tau=1 ms on representative spikes; absolute
and original-channel-standardized V/gE/gI RMS; first differing spike slot.
All zero raw, zero 1-ms, zero cumulative, zero reference, and state-equal cases
are counted separately. Scores of zero remain zero; ratios with zero
comparators are null. Normalized L1 may exceed one and is not an error
probability. No result establishes biological fidelity, a universal failure
of activity guidance, computation saving, or optimal geometry.
