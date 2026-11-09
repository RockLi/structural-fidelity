Synthetic rewiring control — standalone experiment bundle, 2026-10-23

Start with REPORT-zh.txt for findings and limitations. The existing preprint has
not been edited. This folder contains all source, graphs, raw outputs, analysis,
figures, and provenance needed to reproduce the experiment without the old repo.

Requirements
  rustup with toolchain 1.98.1 (rustc); compilation uses edition 2024, opt-level 3.
  Python 3 with NumPy and Matplotlib. Tested: Python 3.13.5, NumPy 2.5.4,
  Matplotlib 3.10.8 on Apple arm64 Darwin. See environment.json.
  A fresh output directory and approximately 200 MB per run bundle.

Full reproduction (replace the source path as needed)

  python3 -B /absolute/path/to/synthetic-rewiring-control-20261023/reproduce.py \
    --output /tmp/synthetic-rewiring-new-run --compare-reference

The output directory must not already exist. The script reconstructs the original
frozen source from source/ plus frozen-inputs/original-overrides/, verifies the
original 55-file manifest, applies the documented experimental changes, compiles,
generates graphs, runs all 360 cases, validates, analyzes new CSV/state files,
renders new figures, and runs the independent audit and post-hoc diagnostics.
--compare-reference also compares fresh graphs, per-slot CSVs, recorded state
payloads, and error CSVs with this bundle. Timings and PDF metadata are excluded
from bitwise equality. Cross-platform bitwise reproducibility is not promised.

The full replay was validated in /private/tmp/synthetic-rewiring-fresh-20261023.
The supplemental audit/diagnostic stage was added to reproduce.py after that
primary replay and then executed and checked separately in the same fresh output.
This sequencing is documented in fresh-reproduction-validation.json. No new
scientific conditions or additional independent samples were added by the replay.

Design
  2 E3 families × (original + 19 rewired graphs) × 3 inputs × 3 execution modes.
  Families: homogeneous, heterogeneous. Inputs: tonic, global_burst, focal_burst.
  Modes: explicit, raw_sum, trace. All proxy cases use 0% explicit retention.
  125 chunks × 100 internally identical units; 300 slots at 0.1 ms.
  protocol.json gives exact constraints, fixed seeds, inputs, and scope.
  experiment-lock.json and analysis-plan-lock.json precede scientific runs.

Key files
  experiment.rs             additive observation driver
  run_experiment.py         source preparation, graph generation, run, validation
  analyze.py                fixed primary analysis and all four figure pairs
  audit_and_diagnostics.py  independent graph/bridge checks and post-hoc diagnostics
  build.patch               two documented modifications to frozen Rust source
  frozen-inputs/            original manifest, source overrides, archived E3 bridge
  graphs/                   all 40 exact graph CSVs
  runs/                     all 360 CSV, compressed state, and metadata triplets
  commands.jsonl, logs/      exact commands and outputs
  analysis/summary.json     summary statistics, with all 19 controls per group
  analysis/wiring-effects.csv           rewired explicit versus original explicit
  analysis/approximation-errors.csv     proxy versus SAME graph explicit
  analysis/topology-error-interactions.csv  paired error summaries
  analysis/posthoc-rate-distributions.*     explicitly post-hoc distribution analysis
  analysis/*.png, *.pdf      publication-friendly figures, regenerated from new runs
  validation.json, independent-audit.json, analysis/metric-audit.json
  fresh-reproduction-validation.json, reproduction-evidence/  replay evidence
  final-validation.json, file-sha256.json                    final delivery checks

Metrics and data layout
  Each CSV row is a slot: spikes, recurrent_messages, active_source_edge_visits,
  active_chunks. Recurrent messages exclude external stimulation. Edge visits are
  recomputed from active source degrees and independently checked.
  Chunk L1: sum_(t,k)|B_other[t,k]-B_ref[t,k]| / sum_(t,k)B_ref[t,k].
  Population L1: sum_t|sum_k B_other[t,k]-sum_k B_ref[t,k]| / sum_(t,k)B_ref[t,k].
  B uses non-overlapping 1 ms bins. Multiply by 100 for percent; values can exceed
  100%. Population L1 <= chunk L1 by construction; the inequality is not a discovery.
  post_stimulus_rate_delta_pct always refers to slots 80–299. For tonic this is a
  late-window measurement, NOT a post-stimulus measurement (tonic input continues).
  Primary rewiring comparisons retain chunk identity. Separate post-hoc sorted
  E/I rate distributions do not retain within-group identity.

  NPZ state_bits has shape [300,125,10], dtype uint32. Fields:
  0 spike count; 1 voltage float bits; 2 g_exc; 3 g_inh; 4 g_longrange;
  5 recovery; 6 local_exc context; 7 local_inh context; 8 refractory_until;
  9 scheduler status (0/1/2). All 100 units per chunk are checked for equality at
  every slot before compact recording. Pending queue contents are not fully saved.
  Instrumented loop times include recording and unequal counting overhead; they
  are logistics metadata, not performance benchmark evidence.

Interpretation guardrails
  Homogeneous controls exactly preserve per-node per-arm in/out degrees and
  incoming/outgoing weight multisets. Heterogeneous controls preserve degree and
  source weight multisets but NOT target weighted strength: report separately.
  Original graphs are already E/I blockrandom graphs. No biological motif claim.
  Fixed-proposal swap chains have no established uniformity or mixing guarantee.
  These are descriptive conditional results, not formal null-model p-values.
  raw_sum retains and traverses all replaced edges and still updates trace/channel
  state in this ablation. Spike equality is observed, internal float equality is not.
  No memory-only ablation or actual graph compression is tested here.
  One original per family, three fixed inputs, 30 ms: no long-time guarantee.

Figures
  wiring-effects: structural changes at population and identified-chunk resolution.
  proxy-errors: raw_sum and trace fidelity against each graph's explicit reference.
  messages-and-error: recurrent message counts versus error; NOT a time-cost plot.
  example-traces: focal_burst with seed 91001, chosen before inspecting outcomes.

All original manuscripts and original repositories were left untouched. This is
an additive experiment package; no external data download is required to rerun it.
