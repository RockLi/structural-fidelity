# Results and figure provenance audit for major revision

Audit date: 22 October 2026. **Current authoritative source for this memo is `/Users/rock/workspace/bettiai/brian2/next-brain/`**, supplied by the user's correction. Earlier inspection of `/Users/rock/workspace/bettiai/next-brain/` found an older scaffold-only trace implementation; that finding is SUPERSEDED and must not be applied to the corrected root. No source modifications or experiment reruns were performed by this audit agent. Parent reproduction agent is obtaining fresh results.

## Highest-priority conclusions

1. The corrected root contains an actual `Stateful` implementation in `src/experiment/lpu_index.rs:311–439`, selected by index mode and harness; closure test `tests/phase3_benchmarks.rs:2299` executes it over E1/E3/E4/E5 and calibration/budget/policy cases. Thus trace results have an executable source, unlike the originally supplied directory.
2. The checked current closure test is at lines 2299–3117, covers E1/E3/E4/E5, and uses the single full-record Hann DFT in `metrics.rs:241–278`. Searches of `tests/*.rs` and metrics found no FF/FB/WTA/Rec/Mixed5 closure protocol or Welch implementation in this exact directory. Any newer experiment package must be separately located, not assumed to be this test.
3. Plots 1–3 and 5 hardcode numerical summaries. The code can generate such results, but stored plotting numbers are secondary evidence, not machine-linked raw trial outputs. Figures should be rebuilt from fresh reproducible exports.
4. Plot 4 loads real numerical CSVs; there is no discovered synthetic spectrum-generating formula. HOWEVER its static curve attribution is wrong: `examples/measure_lpu_resources.rs:141–229` builds calibrated **TwoChannel**, and :739–750/:849–859 exports the `*_lpu.csv` filenames plotted as **Static LPU-4ch** in `plot_paper3_figures.py:583–587`. Do not call the spectra fabricated; correct attribution/provenance instead.
5. The boundary-heavy spectra use **800 E + 200 I = 1,000 units**, not the E3 12,500-unit evaluation network: old explicit/2ch exporter `measure_lpu_resources.rs:763–776`; new stateful exporter `phase3_benchmarks.rs:2738–2759`. Stateful PSD is hybrid with StrongInhibitoryLoop threshold 1.0 (:2753–2779). E1 stateful PSD is pure proxy (:2693–2724).
6. PSD physical units need resolution before retaining any biological gamma or 39 Hz claim: tests :2696 and :2740 set `dt_psd=0.001`, pass it directly to HarnessConfig.dt and directly to metrics functions that explicitly require seconds. Phase-3 benchmark timestep convention is 0.1 **ms**, passed to metric functions after division by 1000 (`phase3_benchmarks.rs:39–44`). `lpu_index.rs:331` interprets scheduler.dt as milliseconds; harness passes config.dt unchanged to Scheduler (:147–158). Existing spectrum frequency labels may therefore be incompatible with the actual kernel time convention. Parent code audit must settle this.
7. Retention policies are edge classes, not detected graph motifs: `retention.rs:140–179`. `StrongInhibitoryLoop` = inhibitory-source edges above threshold; `FastInhibitoryLoop` = thresholded I→I edges, with no delay condition; `ShortCycleMotif` = thresholded E→I edges, with no cycle detection. Rename scientific labels accordingly.
8. `spike_ratio` is neural activity ratio, not computational cost; it algebraically duplicates FR error for matched N, steps, dt. Use actual routed queue messages and measured runtime as separate computational axes.

## Exact metric definitions

- `RunRecord.total_events`: sum of `StepRecord.events_injected` (`harness.rs:85–88`). Step record counts post-step routing/proxy queue insertions (:61–63, explicit :246–264, mixed :524–527). External input insertions are outside this recurrent-routing count. The baseline router also aggregates all source-chunk spikes into one weighted event per outgoing chunk edge (`connectivity/event_router.rs:88–126`); baseline events are NOT individual synaptic spike transmissions.
- `event_ratio = proxy_run.total_events()/explicit_run.total_events()` (`frontier.rs:111–118`). Hybrid numerator includes both retained and proxy routes. It is a recurrent queue-insertion ratio, not a wall-time ratio and not an edge-visit ratio.
- `spike_ratio = sum(proxy total_spikes)/sum(explicit total_spikes)` (`frontier.rs:120–127`).
- `FR[n] = total_spikes[n]/(N*dt_seconds)` (`metrics.rs:145–157`); `mean_fr_hz` is the time average (:47–48). Hence `spike_ratio = 1 + FR_delta_pct/100`. With |FR error|≤20%, the ≤1.5 spike criterion is redundant.
- `PSTH-r`: Pearson correlation of per-simulation-step population-rate samples over the complete equal-length records, with no smoothing, rebinning, onset exclusion, or trial averaging (`metrics.rs:116–127,148–157,210–233`). Name it population-rate trace correlation, not an empirical multi-trial PSTH unless that analysis is actually added.
- `retained_edges_pct = kept chunk edges/all chunk edges *100` (`retention.rs:209–221`, `frontier.rs:160–161`).
- `explicit_event_share_pct = hybrid_explicit_insertions/(hybrid_explicit_insertions+hybrid_proxy_insertions)*100` (`frontier.rs:162–167`). It describes hybrid queue load, not original synaptic traffic carried by the retained edges. Comparing this share with retained edge fraction does NOT establish a subset's disproportionate original network traffic or causal importance.
- Spectrum: demean full trace, multiply by symmetric Hann window, DFT bins 1..N/2, power `(re²+im²)/N²` (`metrics.rs:241–278`). This is a windowed power spectrum; no segment averaging, overlap, sample-rate/window-energy normalization, or doubled one-sided PSD scaling. It is not Welch and power must not be labeled density/Hz.
- Low-frequency difference in plotting code is `100*abs(LF_fraction_proxy-LF_fraction_explicit)` (`plot_paper3_figures.py:576–580`), i.e. **percentage-point difference** in fractions, not a relative percentage error.

## Scientific interpretation of implementation

Stateful output uses raw summed weighted source-spike drive times a bounded/small state-dependent modulation, not the filtered channel state itself (`lpu_index.rs:401–426`). The filters/trace modulate direct input. Causal scheduling at current_slot+1 matches only the tested 1-slot explicit delay; arbitrary edge-specific delays are not represented by the proxy index.

The stateful routine retains and traverses outgoing replaced chunk-edge adjacency (`lpu_index.rs:350–381`). Its event-count advantage comes from target-and-sign queue coalescing. Runtime is at least O(number of chunks + edges from spiking source chunks), not generally O(active chunks). Edge storage compression and source-edge work elimination have not been established. This makes the method closer to a causally aligned, state-modulated event aggregation operator than a learned graph/topology replacement.

The trace alpha is `(dt_ms/20).clamp(.005,.25)` (:336), so the advertised 20 ms history time scale is exact only in the unclamped regime. At dt=.1 ms, alpha=.005; at dt=.001, alpha still=.005. The latter differs by 100× from dt/20; do not use the same physical-time interpretation across those runs without correction.

## Numbers present in artifacts (secondary evidence pending rerun)

### Main stateful endpoints encoded by plot script / manuscript

| Case | Total units | Steps | Kernel dt field | r | FR error % | Source |
|---|---:|---:|---:|---:|---:|---|
| E1 pure stateful | 50,000 | 500 | .1 | .992 | −8.4 | plot :81–84; test :2303–2338 |
| E1 hybrid stateful, 24% retained | 50,000 | 500 | .1 | .980 | −16.0 | plot :85–86; test :2340–2379 |
| E3 heterogeneous hybrid, 11.2% retained | 12,500 | 200 | .1 | .983 | −3.5 | plot :95–96; test :2383–2453 |

The manuscript gives E1 pure event ratio .164. Obtain exact count and ratio from fresh test/export rather than deriving runtime benefit. These endpoints can be main results once reproduction agrees, with explicit status as deterministic finite-window synthetic benchmarks.

### Stateful retention curve encoded in plot script :169–175

| Retained chunk edges % | r | FR error % |
|---:|---:|---:|
| 2.0 | .986 | −2.5 |
| 5.8 | .981 | −4.6 |
| 11.2 | .983 | −3.5 |
| 15.9 | .984 | −4.0 |
| 20.5 | .980 | −4.7 |

Execution source: test :2534–2577; thresholds [2.0,1.75,1.4,1.1,.8], 10k E + 2.5k I, 200 steps. No zero-retention heterogeneous control in this sweep. Supports robustness across these budgets only, not necessity of 2% or a 5–15% optimum.

### Policy comparison encoded in plot script :252–257

| Code label | Correct scientific label | Retained % | Legacy r | Stateful r | Legacy abs FR error % | Stateful abs FR error % |
|---|---|---:|---:|---:|---:|---:|
| StrongInhibitoryLoop | inhibitory-source weight threshold ≥1.0 |17.4|.542|.980|23.0|4.7|
| FastInhibitoryLoop | I→I weight threshold ≥.25 |3.7|.276|.985|157.8|3.1|
| ShortCycleMotif | E→I weight threshold ≥.7 |13.1|.839|.982|59.0|1.0|
| Strong+Fast | union of first two policies |21.1|.491|.979|14.0|4.7|

Test :2579–2628. Unequal budgets preclude attribution to motif identity. Script `ev_share_st=[22.6,15.2,1.1,28.9]` is inherited legacy static telemetry even though variable suffix might suggest stateful; check fresh outputs before reporting as new method. Original manuscript ShortCycle row (~7% edges/~13% traffic) is erroneous relative to the script and closure report, which give 13.1% edges/1.1% legacy explicit queue share.

### Existing numeric spectrum files, directly recalculated

| File | Max-frequency label | Max power | Fraction at frequency label ≤20 |
|---|---:|---:|---:|
| psd_50k_sustained_explicit.csv |1|1.878217|.2323901445|
| psd_50k_sustained_lpu.csv |393|66.23489|.0097599208|
| psd_50k_sustained_stateful.csv |1|1.831269|.2226142628|
| psd_boundaryheavy_explicit.csv |39|60.64434|.0060398811|
| psd_boundaryheavy_lpu.csv |393|66.23489|.0097599205|
| psd_boundaryheavy_stateful.csv |39|57.55438|.0060665785|

These are verified numerical contents, not validated physical-frequency claims. Stateful boundary peak power divided by explicit is 94.9%; that statistic alone does not establish recovered biological oscillations or global spectral fidelity. The two historical proxy spectra have extremely similar powers; no provenance judgment beyond exporter attribution is warranted without reruns.

### Existing pure-proxy frontier CSVs

These are separate gain/tau sweeps (`examples/frontier_report.rs:58–87,155–179`) and NOT the 3×3 hybrid calibration grid. Each CSV has 23 configurations: defaults + seven excitation gains × three fast-excitation time constants. Neither CSV contains a point jointly satisfying r≥.7 and |FR error|≤20%.

| CSV family | Config | r | FR error % | event ratio | neural spike ratio |
|---|---|---:|---:|---:|---:|
| E1 50k | 2ch-default |−.2172|+323.65|.3882|4.2365|
| E1 50k | 4ch-default |.4354|−9.72|.4052|.9028|
| E1 50k | highest-r g2.0/t1.0 |.7525|+113.04|.4057|2.1304|
| E3 12.5k | 2ch-default |.0699|+381.42|.3749|4.8142|
| E3 12.5k | 4ch-default |.6318|+38.96|.6186|1.3896|
| E3 12.5k | highest-r g3.0/t1.0 |.8784|+44.91|.6197|1.4491|

E3 default values in these CSVs differ from plot1 (.014 and .423). Do not mix them into a common frontier without matching topology/seed/duration/config. The E1 CSV itself invalidates an unqualified claim that every tested static configuration has r<.5; its high-r configurations fail rate fidelity instead.

## Recommended revised evidence tables / figure strategy

1. Main benchmark configuration table: exact total N, E/I counts, chunks, seed, connection probabilities/weights, dt convention, steps, physical duration only once unit audit is resolved, external drive, retained fraction.
2. Main outcome table from a single fresh run manifest: explicit, legacy 4ch, causally aligned raw aggregation (new ablation if available), normalized filters without trace (if available), full stateful; r, signed FR error, exact routed queue counts and ratio, repeated timing if available. Do not interpolate missing ablations.
3. Retention-budget table/figure: full stateful across zero + observed positive budgets if reproduction adds zero; plot r and FR error separately and exact routed-event ratio. Remove sweet-zone shading and structural-anchor rule.
4. Unequal-budget policy table may remain descriptive with honest edge-class labels, or move to supplement. Do not title it motif taxonomy or claim independently controlled fidelity dimensions.
5. Spectra should be newly exported from paired same-config runs under one explicit unit convention and estimator. If that cannot be completed this turn, omit the old spectral restoration claims from the main affirmative results and record as unresolved validation, rather than reproducing misleading plots.
6. Legacy SoA speed and 2ch speedups may be contextual supplement if raw provenance exists. No transfer of 1.42×/3.49× speedup to stateful. No speed claim based solely on 83.6% queue-event reduction.
7. E4 excitable r=.559 is below .70 and cannot be called a joint fidelity pass despite ~1% FR error. Test allows ≥.55 (:2890), a different gate. Label phase-specific gates explicitly; passing the test suite is not a blanket pass of one joint criterion.
8. Calibration grids run on 12,500 units, 200 steps (:2630–2689), not 50k. A finite grid establishes tested outcomes, not a structural impossibility/architecture ceiling. 18 plotted grid evaluations include the repeated (2.5,.4) center in two 3×3 grids; if claimed as 18 distinct configs, correct to 17 distinct settings / 18 evaluations.

## Claims safe only after fresh reproduction

- Target-and-sign queue coalescing can preserve synthetic population-rate trajectories in the observed deterministic runs.
- Corrected stateful implementation performs much better than this historical four-channel implementation on tested cases.
- Explicit retention benefits are conditional on the replacement operator; no universal minimum retained fraction is demonstrated.
- Rate agreement and temporal correlation are distinct; routed queue load is a third, separate metric.

## Claims to remove or qualify

- Minimal neural motif, detected short cycle, biological gamma restoration, exact causal mechanism of 393 Hz resonance, universal 5–15% rule, static architectural ceiling, end-to-end speedup of stateful, full E1–E5 stateful coverage (E2 500k trace is not established here), independent triple Go criteria, and any claim of multi-seed statistical certainty.
