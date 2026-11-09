# Independent review: post hoc raw-sum diagnostic

Sources inspected: `/tmp/local-circuit-repro-current` versus `/tmp/local-circuit-repro-diagnostics/raw_sum`; diagnostic patch, full source diff, build commands/logs, closure output, scheduler/event router/chunk delivery code, unchanged benchmark setup, and 300-row exported population-rate trace. No code modified and no experiment rerun by this reviewer.

## Verdict

The diagnostic is a valid control for the dependence of the reported population outputs on trace/channel modulation. No accidental self-comparison, shared simulator state, or instrumentation affecting the neuronal evolution was found. Its result supports a substantially narrower mechanism than the original manuscript: target-and-sign message aggregation with matched delivery timing can preserve the tested population outputs without using filter/trace values in the delivered drive.

Initially the source differed only in two functional assignments (`exc_drive=raw_exc`, `inh_drive=raw_inh`, `src/experiment/lpu_index.rs:409,426`) and read-only output logging in `frontier.rs`. The four-channel and trace states are still allocated and updated, but their values no longer influence injected drive. Thus it demonstrates lack of dynamical necessity of those state-dependent output factors in these tests; it does not by itself measure the runtime/memory saving of removing their computation/storage.

## Why equality is plausible

Explicit and approximate runs construct independent schedulers with matched initialization and input (`harness.rs:221–228,281–287,404–414`). Explicit routes each spiking-source chunk edge with strength `edge.weight * source_spike_sum`; raw aggregation sums those same quantities by destination and source sign (`event_router.rs:103–126`, `lpu_index.rs:350–381`). For these recurrent networks, delay_slots is 1. Both routes schedule at the already incremented current_slot+1. At delivery, the chunk adds due excitatory and inhibitory strengths separately before integrating the neural state (`chunk.rs:173–199`). With exact arithmetic, this batching is associative. Floating-point accumulation order can differ, so bitwise state equality should not be inferred.

All compared `FrontierPoint` callers inspected pass the explicit run and an independently generated proxy/mixed run. Diagnostic logging reads metrics already computed and does not alter records. The library is rebuilt from the diagnostic source and then linked into its test binary; build logs show the expected unused-factor warnings.

## Confirmed numerical findings

- E1 pure raw aggregation: explicit recurrent queue insertions **1,196,827**; raw aggregation insertions **187,953**; ratio **0.1570427471973811** from integer counts; reduction **84.29572528026189%**. Printed f32 ratio is 0.157042742.
- E1 pure and hybrid, E3 homogeneous/heterogeneous hybrid, five retention budgets, four edge-class policies, and medium calibration-grid calls all report **zero mismatched per-step global population spike counts** and equal total spike counts in `logs/closure.log`.
- Independent CSV comparison of the 300-row `docs/phase3/e1_fr_traces_stateful.csv`: `explicit_fr_hz` equals raw diagnostic `stateful_hybrid_fr_hz` for every row, maximum difference 0. Static and calibrated legacy columns do differ, so the exported control is not an all-columns duplicate.

## Wording and evidence limits

1. `StepRecord.total_spikes` is the **global population total**, not per-chunk/group totals or individual spike rasters. Say “the recorded population spike count matched at every simulation step.” Do not say every neuron or chunk spike train matched.
2. In the initial closure log E4/E5 only printed rounded r=1.000 and FR delta=0.0, without per-step mismatch logging; that alone does not establish exact equality. During this review, a reproducer added read-only `DIAGNOSTIC_E45` lines to the test. Use a refreshed log confirming these before extending exact equality to E4/E5.
3. The grid gains no longer enter the delivered raw drive. Equal grid results are an expected redundancy, not 18 independent confirmations of gain robustness.
4. The diagnostic is post hoc. It should be identified as such and should not be described as prespecified.
5. Recurrent queue insertions exclude external stimulus events, edge traversals, per-unit updates, calibration/preparation cost, and remaining queued events after the final simulated step. The 84.30% result is a message-count reduction, not an end-to-end speedup or equal percentage reduction in synaptic computation.
6. Same-sign, same-target, same-delivery-slot additive inputs can be batched in this model; the result does not establish equivalence for heterogeneous delays, synapse-specific state, nonlinear synaptic interactions, plasticity, or cell-specific targeting absent from this chunk-edge model.
7. PSD runs retain the existing ms/seconds ambiguity. Even exact recovery of their numeric spectra does not validate the original 39 Hz biological interpretation.
