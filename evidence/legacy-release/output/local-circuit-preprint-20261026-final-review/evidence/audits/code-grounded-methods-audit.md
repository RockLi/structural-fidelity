# Code-grounded methods and audit for the major revision

Audit date: 22 October 2026. **Authoritative source root for this memo: `/Users/rock/workspace/bettiai/brian2/next-brain`.** This directory was supplied by the user as the corrected implementation. The earlier `/Users/rock/workspace/bettiai/next-brain` checkout is older and contains only a Stateful scaffold; the absence of a working trace in that older checkout must NOT be presented as a defect of the corrected source. No source files were edited. Evidence below comes from executable statements rather than potentially stale comments.

The corrected source has a real `step_stateful` at `src/experiment/lpu_index.rs:320–439`, dispatched by `src/experiment/harness.rs:312–316` and `:449–453`. Contrary to a location description supplied during the task, this inspected implementation calls its state `stateful_traces` and uses a nominal **20 ms** trace, not a `recovery_trace` with 10 ms. `src/lpu/proxy.rs:49–52` still falsely says scaffold; executable code takes precedence. Preserve file hashes in the final provenance manifest because this tree is an untracked directory within a broader Git repository; the enclosing Git HEAD alone does not identify these files.

## 1. What model is actually implemented

The graph nodes are **chunks**, and each `SynapticEdge` links a source chunk to a target chunk. It contains no presynaptic or postsynaptic neuron index (`src/connectivity/types.rs:19–38`). For each spiking source chunk, the explicit path sends **one message per outgoing chunk edge**, with amplitude equal to edge weight multiplied by the total source-chunk spike count (`src/connectivity/event_router.rs:85–126`). Each delivered message is broadcast to every unit in its target chunk (`src/core/chunk.rs:173–187`). Thus the baseline is already a population-to-population broadcast network with individually allocated unit arrays. It is not an explicitly represented heterogeneous neuron-to-neuron connectome.

All units within a chunk have identical initial states (`src/state/mod.rs:39–48`), parameters, and broadcast input. The harness has no within-chunk random initialization or unit-specific drive. Consequently they remain identical under these deterministic updates. A 50,000-unit, 100-unit-per-chunk case has 500 distinct chunk trajectories, not 50,000 independently heterogeneous trajectories. The unit count remains a valid memory/update workload size; it must not be interpreted as an equivalent biological degree-of-freedom count. This is a mathematical consequence of the implementation, not a measured effective-rank estimate.

Even the label “boundary-heavy” needs restraint. The builder excludes self-chunk edges for E→E and I→I regardless of the `forbid_within_chunk` flag; E and I chunk sets are disjoint for benchmark construction (`src/connectivity/microcircuit.rs:162–225`). Hence all generated graph edges are already inter-chunk edges. E3 differs in connection probabilities, weights, seed, and sometimes size, not by introducing boundary crossings absent from E1.

### Manuscript-ready scope paragraph

> We study aggregation of routed interactions in a synthetic chunk-coupled spiking system. Each chunk contains an array of identical units and receives broadcast excitatory and inhibitory inputs. The explicit reference stores a weighted directed graph between chunks and routes one weighted spike-count message along each active source edge. The aggregated implementation preserves the same source-to-target adjacency but combines contributions by target and sign before delivery. The resulting comparisons concern message execution and population-level output in this benchmark; they do not establish faithful reduction of arbitrary neuron-resolved synaptic graphs.

## 2. Exact unit and shared-field equations

Let `n` denote a scheduler slot and `Δ=dt` its numeric integration increment. Let `E_i`, `I_i`, and `L_i` be the three additive input-state variables. Although their identifiers begin with `g`, the equation uses them as additive currents; there are no reversal-potential factors. The kernel is a minimal linear leaky integrate-and-fire-like benchmark, not an Izhikevich model. The `recovery` array is allocated but is not updated or used in the active kernel (`src/state/mod.rs:15–33, 102–135`).

At a stepped slot, all due positive messages are added to every target unit's `E_i`; absolute values of negative messages are added to `I_i`. Let `F_c^E,F_c^I` denote the chunk's separate shared fields at entry. The pre-kernel states are

\[
\widetilde E_i(n)=E_i(n)+U_c^E(n)+0.01F_c^E(n),\qquad
\widetilde I_i(n)=I_i(n)+U_c^I(n)+0.01F_c^I(n).
\]

Here `U` includes delivered external and routed messages. The common input current is `J_i=\widetilde E_i-\widetilde I_i+L_i`. Define `a_i(n)=1` if `refractory_until_i≤n` and zero otherwise. Then

\[
\widetilde v_i=v_i+a_i\Delta(-v_i+J_i),\qquad
(E_i',I_i',L_i')=(1-a_i\Delta)(\widetilde E_i,\widetilde I_i,L_i).
\]

A spike occurs when `a_i=1` and `\widetilde v_i≥30`. On a spike, `v_i'=-65` and `refractory_until_i=n+2`; otherwise `v_i'=\widetilde v_i`. The next slot `n+1` is skipped by the unit kernel, and eligibility resumes at `n+2`. During refractoriness, injected current accumulates but the kernel does not decay input-state variables. Initial `v=-65`, all other floating state zero, refractory deadline zero. The leak equilibrium in this numeric equation is zero, not −65.

Evidence: `src/state/mod.rs:39–48,56–80,102–135`; delivery/shared input: `src/core/chunk.rs:173–199`.

After unit integration, `S_c(n)=Σ_i s_i(n)`, and the shared fields update as

\[
F_c^E(n+1)=\exp(-\Delta/10)F_c^E(n)+S_c(n),\qquad
F_c^I(n+1)=\exp(-\Delta/10)F_c^I(n).
\]

The harness sets `field_decay_tau=10` (`src/experiment/harness.rs:162`). Every chunk—including those designated inhibitory—adds its spikes to the shared **excitatory** field (`src/core/chunk.rs:63–68,201–203`). This common positive self-feedback is present in explicit, two-channel, four-channel, and trace modes; it must not be attributed uniquely to the new proxy. The inhibitory shared field has no spike-driven source here.

### Dormancy

A stepped chunk remains active when it spikes, receives any due event, has a shared field above `10^-6`, or has input state above that threshold (`src/core/chunk.rs:219–231`). The scheduler also keeps a chunk in its active set whenever it has any future event, even if its status has become Pending (`src/core/scheduler.rs:110–125`), so it can step across a future-event waiting period. A skipped chunk executes only `dormant_skip_count += 1` (`src/core/chunk.rs:235–237`): there is no exact jump-ahead propagation. Its voltage and shared/input states are frozen. Residual input/field thresholds make this an approximate inactive-state policy; voltage displacement from its equilibrium is not checked. Scalar/SIMD equivalence does not prove equivalence to an always-stepped simulation.

## 3. Exact event ordering and timing

At each iteration, external input is enqueued, scheduler slot `n` is stepped, and `Scheduler::current_slot` increments to `n+1`. Only then are new spikes routed (`src/experiment/harness.rs:238–264`; `src/core/scheduler.rs:128`). The explicit router queues a message for `(n+1)+edge.delay_slots` (`src/connectivity/event_router.rs:116`). With stored delay one, delivery is at slot `n+2`.

Historical two-channel and four-channel modes queue the post-step drive at the current scheduler slot, namely `n+1` (`src/experiment/lpu_index.rs:283–305,445–464`). The implemented trace mode queues at `current_slot+1=n+2` (`:392–434`), matching the explicit reference for the benchmark's uniform `delay_slots=1`. Do not describe this only as a physical “one-step delay” without stating that the slot counter was already incremented.

`TargetEntry` retains target, weight and sign but **drops the edge delay** (`src/experiment/lpu_index.rs:38–45,89–97`). The trace path hardcodes one additional post-step slot. It therefore does not support faithful aggregation of arbitrary heterogeneous edge delays. A general exact batching baseline would group by target, sign and delivery slot.

## 4. Historical modes

Define the source count `S_c(n)` and chunk size `N_c`; let replaced incoming edges to target `d` of source sign `q` be `P_d^q`.

### Two-channel normalized-count mode

For the normal benchmark mode,

\[
D_d^q(n)=g_q\sum_{(c,d)\in P_d^q}w_{cd}\,S_c(n)/N_c.
\]

One message is enqueued for each positive target/sign total. `FiringCount` instead omits division by `N_c`. `ExponentialDecayField` is exposed by the API, but indexed harness calls pass zero for both field inputs, so that option produces zero drive in this path. Evidence: `src/lpu/aggregator.rs:98–124`; `src/experiment/lpu_index.rs:159–199`. These quantities are spike fractions per slot, not Hz, unless divided by the timestep.

### Historical four-channel mode

For `a∈{fast,slow}`,

\[
x_{d,q,a}(n)=d_{q,a}\,x_{d,q,a}(n-1)+g_{q,a}\sum_{(c,d)\in P_d^q}w_{cd}S_c(n)/N_c,
\quad d_{q,a}=e^{-\Delta/\tau_{q,a}},
\]

with optional omission of population normalization. Output is `D_d^q=x_{d,q,fast}+x_{d,q,slow}` and is injected on every slot with positive channel state, including slots with no new source spikes. Decay is applied once per target per slot, not once per incoming edge (`src/experiment/lpu_index.rs:241–279`; `src/lpu/proxy_params.rs:182–223`). Output then enters the unit's own leaky input-state variables, producing a cascade of filters. Unit-DC normalization changes amplitude but does not mathematically remove the extra filter or its phase response.

Default times in code's ms convention are `(τ_Efast,τ_Eslow,τ_Ifast,τ_Islow)=(3,80,7,80)`, and gains `(1,.5,1,.3)` (`src/lpu/proxy_params.rs:65–80`). Neither mode should be called memoryless at the full-system level: all share unit input states and shared fields, and the four-channel mode has explicit channel memory.

## 5. Exact implemented trace-modulated aggregation

This implementation is not simply historical four-channel output plus one new memory state. It changes input scaling, output construction, gain interpretation, silent-slot behavior, and delay simultaneously. Define **raw weighted input totals**

\[
R_d^q(n)=\sum_{(c,d)\in P_d^q}w_{cd}S_c(n).
\]

There is no division by `N_c`. The `normalize_by_population` flag and slow-channel gains are not consulted by `step_stateful`; the `units_per_chunk` argument is unused. The fast gains are repurposed to choose bounded near-unity multipliers, rather than multiplying channel increments.

All filter states and traces start at zero. For each sign `q` and timescale `a`,

\[
d_{q,a}=\exp[-\Delta/\max(\tau_{q,a},0.1)],\quad
x_{d,q,a}(n)=d_{q,a}x_{d,q,a}(n-1)+(1-d_{q,a})R_d^q(n).
\]

The adaptive input baseline is

\[
\alpha=\operatorname{clip}(\Delta/20,0.005,0.25),\qquad
h_d^q(n)=(1-\alpha)h_d^q(n-1)+\alpha R_d^q(n).
\]

These are traces of **incoming weighted counts** at each target, not traces of its output firing rate or normalized excitatory/inhibitory populations. There are two traces per chunk plus four channel states. The nominal 20 ms interpretation holds near the main benchmark `Δ=.1`; the clamp changes the effective time constant at other steps.

Let `ε=10^-3`. Compute, using the newly updated states,

\[
m_d^q={x_{d,q,fast}-h_d^q\over x_{d,q,fast}+h_d^q+\epsilon},\quad
z_d^q=\operatorname{clip}\!\left({x_{d,q,slow}\over h_d^q+\epsilon},0,1.5\right),
\]
\[
F_d^q=1-0.03m_d^q+0.01(z_d^q-0.5),
\]
\[
\kappa_E=\operatorname{clip}[0.955+0.015\max(g_{E,fast},0.05),0.90,1.08],
\quad
\kappa_I=\operatorname{clip}[0.985+0.045\max(g_{I,fast},0.05),0.90,1.08].
\]

The delivered drive is

\[
D_d^q(n)=\kappa_qF_d^q(n)R_d^q(n),
\]

and is queued for `n+2` only when `R_d^q(n)>0`. E and I totals are delivered as separate positive/negative messages. **No residual drive is injected on a silent-input slot**, although the filter and baseline states continue to decay. Evidence: `src/experiment/lpu_index.rs:331–438`; trace recurrence `src/lpu/proxy.rs:88–90`.

For nonnegative counts and weights, `m∈[−1,1]`, `z∈[0,1.5]`, hence `F∈[0.965,1.04]`. At the manuscript's `g_Efast=2.5,g_Ifast=.4`, the actual multipliers are `κ_E=.9925,κ_I=1.003`. The method is therefore a nearly raw, causally aligned message sum with small history-dependent amplitude corrections. It is not a deep low-pass surrogate whose summed channel output replaces current input.

The code comment “charge-conserving” is not an exact invariant. At constant positive input, the filter/baseline values approach `R`, `m→0`, `z≈1`, so `F≈1.005`, not exactly one. The numerical bounds also permit changes in integrated charge. A claim of exact charge conservation or zero steady-state bias should be removed or replaced by a directly tested approximate statement.

### Manuscript-ready interpretation paragraph

> The final variant separates instantaneous aggregate input from its temporal descriptors. Four unit-DC-gain exponential filters and two adaptive baselines describe recent incoming weighted spike counts. Bounded contrasts between these descriptors provide a small multiplicative correction to the current aggregate. Historical state alone does not emit a message: a target/sign channel produces output only when new weighted input is present. We therefore refer to this implementation as trace-modulated message aggregation. Its comparison with the historical four-channel implementation is a comparison of complete execution designs, rather than an isolated test of adding memory.

## 6. Structural retention is edge-class selection, not motif detection

`src/experiment/retention.rs:141–180` performs the following actual tests:

| API label | Actual predicate |
| --- | --- |
| `StrongInhibitoryLoop` | Source inhibitory and weight ≥ cutoff; no target-E condition and no loop/reciprocity test |
| `FastInhibitoryLoop` | Source inhibitory, target in inhibitory set, weight ≥ cutoff; no delay or recurrence check |
| `ShortCycleMotif` | Source excitatory, target in inhibitory set, weight ≥ cutoff; no reverse-edge or cycle check |
| `HighWeightEdge` | Weight ≥ cutoff |
| `BoundaryHeavyEdge` | Source and target chunks differ |

For some particular weight settings the strong-inhibitory rule selects only I→E edges because I→I weights fall below the cutoff, but that is a property of that dataset, not the predicate. Use labels such as “strong inhibitory-source edges,” “I→I edges,” and “E→I edges” in the revised text; preserve API labels in a reproducibility table if needed. No experiment here identifies irreducible graph motifs.

The kept and replaced sets are disjoint (`:191–205`), and mixed execution uses their separate router/index. It is inaccurate to claim that explicit retained inhibitory edges and the proxy **necessarily double-count the same edges**; a gain mismatch is a possible explanation, not literal edge duplication.

## 7. Cost, memory, and exact batching control

The adjacency index stores **one `TargetEntry` for every replaced edge** (`src/experiment/lpu_index.rs:89–97`). At each step it scans source entries, sums per-unit spike flags for sources with outgoing edges, then traverses outgoing edges of spiking sources. It also clears target accumulators and updates channel states over **all** chunks. Complexity is at least `O(C + N_source_scan + Σ_{c spiking} outdegree(c))`, plus scheduling and target delivery. It is not `O(active chunks)` independent of graph degree or total sources. An explicit message incurs a target-unit loop at delivery, whereas target/sign batching amortizes that loop across multiple source contributions.

The configuration keeps both `replaced_circuit` and its derived index (`src/experiment/harness.rs:713–715`), so this does not by itself demonstrate removal of connectivity memory. Total memory must include both representations, queue storage and allocator overhead. The reported 32 B/unit is only six `f32` arrays and one `u64` array (`src/state/mod.rs:176–181`), including an unused recovery array; it is not bytes per complete modeled neuron including graph/events.

`RunRecord.total_events` counts post-step routed/injected messages (`src/experiment/harness.rs:61–64,85–88`), excluding external protocol messages. `SchedulerStepMetrics.event_count` counts messages delivered this slot, a distinct quantity. Do not use injected counts as delivered counts at finite simulation boundaries.

`FrontierPoint.spike_ratio` is exactly total proxy neural spikes divided by total reference neural spikes. For equal durations and unit counts it equals `1 + mean_fr_delta_pct/100`. This is activity fidelity, not an independent computational cost. The code's three Go criteria (`src/experiment/frontier.rs:182–185`) contain a redundant upper-spike criterion whenever |rate error|≤20%.

### Essential exact aggregation baseline

For this common-delay chunk-broadcast model, grouping messages by target, sign and delivery slot and retaining their exact summed amplitude commutes with linear input addition. Thus the control `D_d^q=R_d^q` with the reference delivery slot preserves the input sequence, up to floating-point summation order. It should preserve the deterministic neural trajectory unless tiny rounding changes a threshold. It achieves message-count reduction without deleting graph interactions or using an adaptive trace. This is an algebraic observation, not a completed experimental result in this memo.

The revised study should compare explicit routing, exact delayed batching, bounded static-gain batching (`κR`), and full trace modulation. This comparison tests whether dynamic modulation adds fidelity or merely perturbs an already sufficient batching operation. An isolated experiment should additionally fix source normalization, delay, output gating and gain mapping while varying only the dynamic descriptors. The original “three-factor” ablation proposal is insufficient because the inspected design changes more than three factors.

## 8. Metric and spectrum provenance corrections

Main Phase 3 benchmarks set `DT_MS=.1` and explicitly pass `DT_S=.0001` to dynamics methods (`tests/phase3_benchmarks.rs:39–46`). E1 uses 500 steps, hence **50 ms**, despite stale `//500 ms` comment at line 157. Stateful E3 hetero uses 200 steps, hence **20 ms** (`:2389–2401,2408–2427`); E3 homogeneous uses 300 steps, hence 30 ms (`:2475–2480`). These are short transient windows, not long-duration stationary tests.

The rate trace contains one value per simulator step, `R_n=S_n/(N dt_seconds)`, with no smoothing, multi-step binning or trial averaging (`src/experiment/metrics.rs:145–157`). Pearson r is computed at zero lag over equal-length raw traces (`:116–127,209–233`). Calling it population-rate trace correlation is clearer than suggesting a trial-averaged PSTH. `CV_pop` is the standard deviation of this aggregate rate over time divided by its mean (`:50–63`), not single-unit ISI CV or direct pairwise synchrony.

The code spectrum is a demeaned **single whole-trace Hann-windowed DFT**, using `|DFT|²/N²` and omitting the DC bin (`src/experiment/metrics.rs:160–206,241–277`). There is no Welch segmentation/averaging in the inspected generator. The normalization is not a conventional spectral density in units per Hz; label it normalized spectral power or implement and document a density estimator.

Two severe problems apply to the old manuscript's spectral figure:

1. `examples/measure_lpu_resources.rs:214–225` constructs **TwoChannel** calibrated mixed/LPU configurations, and exports `psd_*_lpu.csv` at `:739–750,849–859`. `docs/phase3/plot_paper3_figures.py:534–563` labels those CSVs as “Static LPU-4ch.” The visible generator therefore does not support that label. Do not reassign provenance based solely on the curve appearance.
2. Spectral export passes the same `dt_psd=.001` to `HarnessConfig.dt`, documented and used by proxy decay as milliseconds, and to `get_fr_trace`/`compute_psd_spectrum`, which require seconds (`tests/phase3_benchmarks.rs:2696–2724,2740–2783`; legacy generator has the same inconsistency). This differs from the main suite's explicit ms→s conversion. Under the current simulator-ms convention, reported Hz are off by a factor of 1000. If a separate dimensionless or seconds convention is intended, channel constants and all physiological interpretations must be remapped explicitly. The existing 39 Hz “gamma restoration” and 393 Hz artifact interpretations are not established.

The boundary spectral run also contains only 800 E + 200 I units / 10 chunks with a different probability configuration (`tests/phase3_benchmarks.rs:2738–2778`), not the E3 12.5k /125-chunk topology in the main table. The trace clamp is active at `.001`, giving `α=.005`; its physical baseline timescale therefore differs from the advertised 20 ms if one follows the ms convention.

### Manuscript-ready limitations paragraph

> The present tests use synthetic chunk-level broadcast connectivity and identical units within each chunk. They assess reproduction of aggregate output within specific short test windows, not preservation of heterogeneous single-neuron timing or biological circuit function. Retention rules select edge classes rather than verified reciprocal motifs. The indexed implementation retains the replaced adjacency, so queue-event savings should not be interpreted as topology-memory elimination. Historical spectral exports use inconsistent time-unit conventions and model labels; we exclude their physiological frequency claims pending regenerated, provenance-linked analyses.

## 9. Recommended main-paper claims supported by this audit

- A reproducible software framework compares per-edge chunk messages, target/sign aggregation and disjoint hybrid routing.
- The corrected final implementation aligns delivery with the tested uniform-delay reference and uses near-unity, history-dependent modulation of raw aggregate input.
- High trace correlations, if reproduced, establish similarity for the specified synthetic tests, not the isolated necessity of adaptive memory.
- Structural-retention benefits must be re-evaluated against exact delayed batching and matched edge-class controls before claiming motif necessity.
- Measured queue reduction, measured wall time and memory footprint are separate axes. None can be inferred from neural spike reduction alone.

This memo does not certify a physiological LIF parameterization, arbitrary-delay correctness, long-time stationarity, cross-seed generalization, exact dormant stepping, or new experimental outcomes.

## 10. Concise protocol table for manuscript use

All main-suite rows below use 100 units per chunk and `Δ=.1 ms`, with `dt_seconds=.0001` passed to metrics. External drive is applied to E chunks. Main comparisons use one specified seed per topology; this is not a seed ensemble.

| Workload | Allocated E + I units | Chunks | Slots / duration | Input / graph |
| --- | --- | --- | --- | --- |
| E1 sustained | 40,000 + 10,000 | 400 + 100 | 500 / 50 ms | Tonic amplitude 10; balanced spec seed 42; p=(.10,.20,.20,.15), w=(.8,.8,1.2,.6) in EE,EI,IE,II order |
| E3 heterogeneous | 10,000 + 2,500 | 100 + 25 | 200 / 20 ms | Tonic 10; seed 200; p=(.15,.25,.25,.20), base w=(.6,.8,1.4,.5), per-edge uniform ±50% weight spread |
| E3 homogeneous | 10,000 + 2,500 | 100 + 25 | 300 / 30 ms | Tonic 10; seed 99; same p and base w as E3 hetero, no spread |
| E4 weight regimes | 4,000 + 1,000 | 40 + 10 | 200 / 20 ms | Tonic 10; p=(.10,.20,.20,.15), seed 42. Stable w=(.3,.5,1.6,.3); balanced=(.8,.8,1.2,.6); excitable=(1.2,1.0,.8,.4) |
| E5 perturbation–recovery | 4,000 + 1,000 | 40 + 10 | 300 / 30 ms | First 80 slots (8 ms) amplitude150, next220 slots (22 ms) no external drive; p=(.10,.30,.30,.15), w=(.3,1.0,1.8,.4), seed55 |

E3 trace retention curve thresholds on inhibitory-source weights are 2.0,1.75,1.4,1.1,.8 (`tests/phase3_benchmarks.rs:2535–2575`). E4 trace retains inhibitory-source edges with threshold `.8*w_IE` (`:2851`); E5 uses1.5 (`:2944`). E4's executable assertion is |rate error|≤5% and r≥.55 (`:2890`), not the general joint r≥.70 criterion. The E5 code's quantities `burst_exp`,`quiet_exp` divide total population spikes only by window length; they are population spikes per slot, not mean per-neuron Hz (`:2971–2980`). “Panic” is an internal workload name, not evidence for an affective or clinical mechanism. “Two phases” is accurate for the implemented burst and recovery protocol, despite comments saying three-phase.

Evidence for rows: `tests/phase3_benchmarks.rs:2303–2337,2383–2427,2455–2480,2802–2879,2894–2969`; balanced/hetero graph constructors `src/connectivity/microcircuit.rs:84–129`; external tonic amplitudes `src/experiment/input_protocol.rs:76–85`.
