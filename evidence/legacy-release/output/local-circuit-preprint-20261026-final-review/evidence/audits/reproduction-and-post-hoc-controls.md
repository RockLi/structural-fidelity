# Rust reproduction and post-hoc diagnostics — 22 October 2026

## Authoritative source and provenance

Authoritative source: `/Users/rock/workspace/bettiai/brian2/next-brain`. The initial `/Users/rock/workspace/bettiai/next-brain` path was an older copy and is **not** the source for the findings below. It was abandoned when the corrected source was supplied. No production files were modified.

The authoritative `next-brain` directory is untracked inside its parent Brian2 checkout, whose HEAD is `f73dcb20ca8c18b0b9f0427f119e33e67873742b`. Consequently the parent SHA does not identify this Rust source. File-by-file SHA-256s (55 source/build/test files) provide the actual freeze: `/tmp/local-circuit-repro-current/source-sha256.json`. Final source-unchanged verification found no changed files. No ancestor or scoped AGENTS.md was found while copying the source.

Environment: Apple arm64 Darwin, rustc 1.86.0 (05f9846f8 2025-03-31), cargo 1.86.0 (adf9b6ad1 2025-02-28). Full metadata is in `provenance.json`.

`cargo test --locked --offline` on the initial copy could not fetch a missing dev-only Criterion dependency (`aho-corasick 1.1.4`). The core has zero runtime dependencies. The authoritative source was therefore compiled directly, without editing it, using `rustc --edition=2024 -C opt-level=3 --crate-name next_brain --crate-type lib src/lib.rs`, followed by `rustc --test --extern next_brain=...` for each test file. All runs used `--nocapture --test-threads=1`. This is an optimized rustc build, not an assertion that the exact Cargo release invocation succeeded.

## Unmodified test reproduction

The unmodified authoritative snapshot passed 86 tests across the library and all six integration-test targets listed below, with one intentionally ignored 500k test. The stateful closure was additionally run alone and passed. No 100M or 500k benchmark was run.

| Target | Passed | Ignored |
|---|---:|---:|
| library | 23 | 0 |
| phase1_fidelity | 2 | 0 |
| phase2_connectivity | 7 | 0 |
| phase2_lpu | 13 | 0 |
| phase2_examples | 9 | 0 |
| stage14_api | 13 | 0 |
| phase3_benchmarks | 19 | 1 |

Full logs: `/tmp/local-circuit-repro-current/logs/`. The complete phase3 suite reported 2.66 s, and the separate closure 1.39 s, including all test work; these are not per-method simulation timings or speedup measurements. The launch process recorded 2.663 s and 1.730 s respectively. Compilation and run commands/times are in `logs/build-results.json` and `logs/run-results.json`.

The current stateful implementation reproduces the manuscript's main rounded values: E1 pure r=0.992, rate error −8.4%, event ratio 0.164; E1 hybrid r=0.980; E3 heterogeneous hybrid r=0.983; E3 homogeneous hybrid r=0.972; E4 stable/balanced/excitable r=0.775/0.904/0.559; E5 r=0.973. The raw rounded transcript-derived table has 72 rows in `metrics-rounded.csv` and `.json`. Printed `spike_ratio` is an activity ratio, not computational cost.

## Actual run duration and sample dimensions

All fidelity rows below use dt=0.1 ms, 100 units per chunk, and a single deterministic graph/drive setting (not independent replications).

| Family | Units | Chunks | Steps | Duration |
|---|---:|---:|---:|---:|
| E1 full | 50,000 | 500 | 500 | 50 ms |
| E1 medium calibration | 12,500 | 125 | 200 | 20 ms |
| E1 trajectory export | 12,500 | 125 | 300 | 30 ms |
| E3 heterogeneous / budgets / motifs | 12,500 | 125 | 200 | 20 ms |
| E3 homogeneous | 12,500 | 125 | 300 | 30 ms |
| E4 each of three regimes | 5,000 | 50 | 200 | 20 ms |
| E5 perturbation | 5,000 | 50 | 300 | 30 ms (8 ms burst, 22 ms quiet) |

The E1 `500 ms` comment is wrong: 500 steps ×0.1 ms =50 ms. E5's printed `burst` and `quiet` values are total population spikes per slot; multiplying by 2 converts them to per-unit Hz for this N=5000, dt=.1 ms setting. They must not be copied as Hz unchanged.

## Critical PSD invalidation

The closure's PSD exports (phase3 lines2696–2799) set `dt_psd=0.001`, pass it into `HarnessConfig.dt` (milliseconds), then pass the identical number into `get_fr_trace`, `compute_psd_spectrum` and `PopulationDynamics::from_record` (seconds). The simulated 1000-slot horizon is therefore 1 ms, but is analyzed as 1 s. The test reproduces the reported 39.0 Hz and1.0 Hz numeric labels, but those labels are wrong by1000×. The corresponding bins are39 kHz and1 kHz under actual simulation time, and FR magnitudes are also understated1000×. Current spectral code is a demeaned Hann-windowed whole-record DFT, not Welch averaging.

This is not corrected by relabeling a gamma claim: the physical simulation must be rerun with consistent units and a suitable duration before making a biological gamma claim. The exported spectrum files are retained as exact historical outputs, not valid evidence of gamma recovery. The E1/E3 fidelity metrics use `DT_S=DT_MS/1000` and are not affected by this particular unit mistake.

## Newly added post-hoc controls

After inspecting the implementation, the parent researcher authorized two diagnostics in isolated `/tmp` copies, with **no production edits**. Every scientific network, drive, seed, duration and retention policy remains the existing closure's configuration. These are post-hoc controls, not held-out validation.

1. `raw_sum`: replace only the stateful branch's output assignments with `exc_drive=raw_exc` and `inh_drive=raw_inh`, retaining the existing one-slot delay and emission only for positive current raw input. All state/history update code remains in the source, although the optimizer may eliminate dead work. Therefore no optimized raw-batching runtime claim is made.
2. `kappa_only`: output `kappa_exc*raw_exc`, `kappa_inh*raw_inh`, retaining the near-unit static kappa transformation but removing the history-dependent output filter. State/history update code again remains.
3. `original_instrumented`: restore the original dynamics and add only output instrumentation so original counts and metrics have identical audit fields.

Instrumentation records integer total recurrent event counts, integer total spike counts, per-slot population spike-count mismatches, maximum per-slot spike-count difference, Pearson r and relative mean-rate error. It does not check neuron-by-neuron spike identity, membrane voltage, queue state, or every internal state variable. Labels inside the inherited test still say `4ch+trace`; the `variant` column identifies what actually ran.

The raw-sum control passes the complete unchanged closure, and original-instrumented does too. Kappa-only initially failed the inherited PSD39-Hz assertion (reported438-Hz label); this failure is preserved in `kappa_only/logs/closure.log`. To reach the remaining E4/E5 probes, the already-known invalid PSD assertion was replaced by a logged warning **only in that isolated diagnostic copy**, after recording the failure. The continuation's success is not a claim that the original kappa-only test passed. Complete diffs and hashes are under each variant directory; commands and timings are in `run-results-complete.json`.

## Exact population-count comparison

| Case | Method | r | Rate error % | Explicit events | Method events | Differing slots |
|---|---|---:|---:|---:|---:|---:|
| E1 50k / 4ch+trace (pure) | original_instrumented | 0.991984189 | -8.385210 | 1196827 | 196584 | 426 |
| E1 50k / 4ch+trace (hybrid) | original_instrumented | 0.980337560 | -15.973608 | 1196827 | 540280 | 428 |
| E3 heterogeneous / 4ch+trace-strong-inh (11.2%) | original_instrumented | 0.983483136 | -3.453818 | 32247 | 21221 | 148 |
| E3 homogeneous / 4ch+trace-strong-inh (homo, 22.8%) | original_instrumented | 0.971557558 | -0.313679 | 43007 | 35356 | 224 |
| E4 stable / stable | original_instrumented | 0.774692178 | +3.465347 | 4374 | 4112 | 152 |
| E4 balanced / balanced | original_instrumented | 0.903518200 | -1.287554 | 8448 | 7600 | 144 |
| E4 excitable / excitable | original_instrumented | 0.558955610 | -0.951123 | 23468 | 15040 | 181 |
| E5 perturbation / E5 | original_instrumented | 0.973404348 | -0.254449 | 16187 | 14369 | 171 |
| E1 50k / 4ch+trace (pure) | raw_sum | 1.000000000 | +0.000000 | 1196827 | 187953 | 0 |
| E1 50k / 4ch+trace (hybrid) | raw_sum | 1.000000000 | +0.000000 | 1196827 | 591580 | 0 |
| E3 heterogeneous / 4ch+trace-strong-inh (11.2%) | raw_sum | 1.000000000 | +0.000000 | 32247 | 21663 | 0 |
| E3 homogeneous / 4ch+trace-strong-inh (homo, 22.8%) | raw_sum | 1.000000000 | +0.000000 | 43007 | 35564 | 0 |
| E4 stable / stable | raw_sum | 1.000000000 | +0.000000 | 4374 | 4009 | 0 |
| E4 balanced / balanced | raw_sum | 1.000000000 | +0.000000 | 8448 | 7638 | 0 |
| E4 excitable / excitable | raw_sum | 1.000000000 | +0.000000 | 23468 | 15059 | 0 |
| E5 perturbation / E5 | raw_sum | 1.000000000 | +0.000000 | 16187 | 14423 | 0 |
| E1 50k / 4ch+trace (pure) | kappa_only | 0.996160507 | -5.901392 | 1196827 | 190238 | 439 |
| E1 50k / 4ch+trace (hybrid) | kappa_only | 0.997698665 | -4.071211 | 1196827 | 583855 | 421 |
| E3 heterogeneous / 4ch+trace-strong-inh (11.2%) | kappa_only | 0.990568042 | -2.329319 | 32247 | 21206 | 130 |
| E3 homogeneous / 4ch+trace-strong-inh (homo, 22.8%) | kappa_only | 0.977614343 | +1.819316 | 43007 | 36175 | 222 |
| E4 stable / stable | kappa_only | 0.844443202 | +2.970297 | 4374 | 4147 | 143 |
| E4 balanced / balanced | kappa_only | 0.895029545 | -1.373391 | 8448 | 7543 | 157 |
| E4 excitable / excitable | kappa_only | 0.625237286 | -0.396301 | 23468 | 15147 | 182 |
| E5 perturbation / E5 | kappa_only | 0.986719728 | -0.063609 | 16187 | 14411 | 132 |

Raw delayed batching yields identical per-slot population spike counts throughout all audited E1/E3/E4/E5 paired runs. This includes all E3 retention budgets and policies, not only the representative rows above. E1 pure batching reduces counted recurrent queue injections from1,196,827 to187,953 (84.2957%) while preserving1,606,400 emitted spikes exactly at the per-slot population level. Current stateful E1 pure injects196,584 events (83.5746% reduction), with1,471,700 spikes and426/500 differing population-count slots.

Kappa-only improves E1 pure r from0.991984189 to0.996160507 and rate error from−8.3852% to−5.9014%; it is still inferior to the raw control's exact population-count result. Similar raw-control exact agreement holds at every audited E3 retention level and in E4/E5. These controls do not support the claim that adaptive history or retaining a specific motif is necessary for the measured fidelity of this chunk-broadcast implementation.

Interpretation is bounded: the implementation's edges are chunk-to-chunk weighted broadcasts, and tested delays are all one slot. Event batching can conserve the delivered sum under those semantics. This result must not be generalized to arbitrary neuron-pair heterogeneous weights/delays, dendritic states, plasticity, or a discovered minimal biological motif.

## Data deliverables

- `/tmp/local-circuit-repro-current/metrics-rounded.csv` and `.json`:72 unmodified-suite printed result rows.
- `/tmp/local-circuit-repro-diagnostics/primary-comparison-exact.csv` and `.json`:24 rows (8 paired settings ×3 variants), full counts and recorded9-decimal metrics.
- `/tmp/local-circuit-repro-diagnostics/diagnostic-results-exact.csv` and `.json`:111 diagnostic rows including calibration and retention cases.
- `/tmp/local-circuit-repro-current/logs/`:unmodified source full test output.
- `/tmp/local-circuit-repro-diagnostics/*/logs/closure-complete.log`:audit outputs including E4/E5 mismatch counters.
- `/tmp/local-circuit-repro-diagnostics/*/diagnostic-complete.patch`:all isolated diagnostic edits relative to the frozen source.
- `/tmp/run_local_circuit_diagnostics.py`, `/tmp/complete_local_circuit_diagnostics.py`, `/tmp/extract_local_circuit_results.py`:diagnostic creation, compilation, execution and parsing scripts.

Caveats: metrics are deterministic within the tested single configurations, not means over biological realizations; no confidence intervals or between-seed generality are established. Recurrent queue-injection count excludes drive events and does not equal total FLOPs, memory, delivery count or wall time. No speedup is inferred from event reductions. The current corrected path was verified read-only against its original hashes after the runs.
