Finite-horizon perturbation/recovery follow-up — 2026-10-23

Start with REPORT-zh.txt for results and interpretation, MODEL-AUDIT-zh.txt for
the audited kernel semantics. This package does not update the preprint.

Scope
  Frozen original graph plus 15 conditional rewires; 125 chunks x 100 identical
  units; explicit routing only; 100 ms at dt=0.1. Baseline, amplitude 1.5 and
  amplitude 3.0 yield 48 new conditions. The old 48 explicit trajectories are
  included as archived inputs for phase diagnosis and training-only predictors.
  They are not new runs and are not 48 independent original networks.

Fresh scientific reproduction
  Requires Python with NumPy and Matplotlib, and rustup toolchain 1.98.1.
  Tested: Python 3.13.5, NumPy 2.5.4, Matplotlib 3.10.8 on Apple arm64 Darwin.
  The Rust library/tests are compiled directly, edition=2024, opt-level=3.
  No Cargo dependency download is used. The frozen Rust compiler is selected
  explicitly by study.py, not inferred from the user's default rustc.

  From this directory, choose an OUTPUT directory that does not yet exist:

    python3 -B reproduce.py --output /absolute/path/to/new-output --compare-reference
    python3 -B render_report_figures.py --root /absolute/path/to/new-output

  The first command copies frozen inputs, recomputes old phase diagnostics and
  training predictors, audits/builds the kernel, verifies a historical bridge,
  runs all 48 conditions, verifies payloads, analyzes, and renders five initial
  diagnostic figures. --compare-reference compares all 48 state arrays and
  count CSVs, and all analysis/phase/predictor CSVs with this archived reference.
  The second command renders two legible report figures from the resulting CSVs;
  it does not simulate, fit, or change any scientific outputs.

  Do not call prepare/run/analyze directly on the completed archive: their
  assertions protect the frozen files from accidental overwrite. A fresh output
  directory is the intended rerun interface. Exact same-environment replay was
  verified; cross-platform SVD, floating point and CSV byte equality are not
  guaranteed. PNG/PDF metadata need not be byte identical across environments.
  Allow roughly 150–250 MB output space plus dependencies and this archive.

Provenance and locks
  experiment-lock.json: primary protocol, analysis scripts, source, graphs,
    training inputs and predictors hashed before the new scientific runs.
  inherited-inputs-sha256.json: inherited source/graph/legacy-input identity.
  inherited-library.patch: earlier canonical routing/raw-sum changes already
    present in source/. No new library changes were made this round.
    experiment.rs retains a historical header referring to build.patch; the
    actual supplied provenance filename is inherited-library.patch.
  run-complete.json: the 48 reference count and compressed-state checksums.
  analysis/analysis-complete.json: reference scientific output checksums.
  render_report_figures.py/report_figures/: presentation-only additions after
    the primary analysis; no claim these layouts were fixed before results.
  reproduction-evidence/: full fresh-run PASS and matching-output evidence.
  PACKAGE-MANIFEST.json: delivery checksums (excludes itself, build/cache files).
  Run python3 -B verify_package.py for a read-only integrity check of the archive.

The supplied graphs are frozen experimental inputs. This package reruns their
dynamics, not the prior graph sampler. Sampling constraints, partitions and
selection rule are in legacy_inputs/protocol.json. The inherited first-hit
sampler is not a uniform null sampler; all 15 rewires share one original graph.

Main outputs
  analysis/response-outcomes.csv: 32 nonbaseline responses, including original;
    own_response_rms differs from response_fidelity (error vs original response).
    relative_response_fidelity=1 is the zero-response comparator, not success.
  analysis/phase-diagnostics.csv: 48 conditions x 8 overlapping diagnostic windows.
  analysis/prediction-associations.csv: fixed predictors, all15/within-arm/without-
    one-arm subsets, separate amplitudes; no p-values. Blank correlation denotes
    constant/near-constant predictor or outcome. Do not count subsets as replication.
  analysis/prediction-data.csv: the 30 graph/amplitude rows used for prediction.
  analysis/source-subspace-coverage.csv: held-out stimulus coverage; no refitting.
  analysis/amplitude-linearity.csv: double response vs twice small, 16 graphs.
  analysis/model-health.csv, baseline-errors.csv, curves-1ms.csv: model-scale,
    baseline-trajectory and time-resolved diagnostics.
  legacy_diagnostics/: old three-phase errors/distributions/status and summary.
  report_figures/: report PNGs and PDFs, rendered from saved CSVs/JSON.

Array and count schema
  runs/GRAPH__CONDITION.npz contains state_bits, uint32 [1000,125,14].
  Fields: 0 chunk spike count; 1 V; 2 gE; 3 gI; 4 gL; 5 recovery;
    6 local E field; 7 local I field; 8 post-update refractory_until;
    9 post-step status (0 Dormant, 1 Active, 2 PendingWakeUp);
    10 pre-update refractory_until; 11 actually_stepped;
    12 refractory kernel skipped; 13 due events before the step.
  Fields 1–7 are IEEE float32 bits, not integer values; decode, e.g.:
    x = numpy.ascontiguousarray(state_bits[:,:,1:4]).view(numpy.float32)
  Old legacy arrays contain only fields 0–9 and 300 time slots. The bridge
  contains 14 fields over the old 300-slot original/module_burst run.
  Row n is recorded after slot n, at completed time (n+1)*0.1 ms. Intervals in
  protocol.json are half-open integer slot ranges. Full pending queues are not
  serialized. A post-step status is not a substitute for actually_stepped.

  runs/GRAPH__CONDITION.csv: step,spikes,recurrent_messages,
    active_source_edge_visits,stepped_chunks,refractory_skipped_chunks,due_events.
  runs/*.json: timing and dimensions; instrumented time is NOT a speed benchmark.
  graphs/*.csv: arm,source,target,weight_bits,delay. Arm 0/1/2/3 = EE/EI/IE/II.

Interpretation details
  V and g are uncalibrated coordinates in a placeholder current-like kernel.
  Refractory at n sets until=n+2, skips only n+1; arriving input still accumulates.
  Main scales/bases are fitted only on old original/module_burst. State PCA and
  source-activity SVD are different objects, neither a nonlinear manifold estimate.
  Recovery is searched AFTER pulse end and the global peak, requiring all remaining
  samples <=5% peak and at least 50 remaining samples. The protocol's shorter text
  omits 'after pulse end'; including it changes none of the 32 outcomes. This is
  finite-window empirical recovery, not a stability or attractor proof.
  Statistical predictors were fixed locally before new simulations, not externally
  preregistered. New stimulus on the same graphs is not unseen-network validation.

All results are deterministic for the checked execution path and environment;
reproducibility of this implementation does not establish biological validity,
time-step convergence, generalization, or scientific superiority of a geometry.
