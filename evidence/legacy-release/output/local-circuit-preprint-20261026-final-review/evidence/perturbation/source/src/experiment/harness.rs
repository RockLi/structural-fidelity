//! Explicit-vs-LPU experiment harness (Task 3).
//!
//! Provides a paired execution framework for running the same network under
//! two matched modes:
//!
//! - **Mode A (Explicit)**: local micro-edges are represented directly via
//!   `EventRouter`. Each spike event is individually routed to target chunks
//!   after each scheduler step.
//!
//! - **Mode B (LPU)**: selected local edges are replaced by proxy channels.
//!   The `LocalFieldAggregator` aggregates source-chunk spike output and
//!   propagates the summed drive to target chunks following the same
//!   projection topology as the replaced explicit edges.
//!
//! # Correctness invariants
//! - Both modes share identical initial state, external input, chunk partitioning,
//!   and scheduler timing.
//! - In LPU mode, drive is propagated *inter-chunk* from source to target
//!   (not self-injected), so Mode B is a compressed representation of the
//!   same topology as Mode A, not a decoupled system.
//! - Event counting is performed *after* routing (post-step spike state), so
//!   `StepRecord::events_injected` reflects the routes triggered by the spikes
//!   that were emitted in the current step.
//! - `StepRecord::slot` stores the scheduler slot *after* `step()` completes
//!   (i.e., `current_slot` which has already been incremented by `step()`).

use crate::connectivity::event_router::EventRouter;
use crate::connectivity::microcircuit::EIMicrocircuit;
use crate::connectivity::types::PopulationType;
use crate::core::chunk::{Chunk, ChunkId, GridCoord};
use crate::core::scheduler::Scheduler;
use crate::experiment::input_protocol::InputProtocol;
use crate::experiment::lpu_index::LpuTopologyIndex;
use crate::lpu::aggregator::{AggregatorParams, compute_lpu_drive};
// Phase 3 imports
use crate::lpu::proxy::ProxyMode;
use crate::lpu::proxy_params::RicherProxyParams;

/// Execution mode for the harness.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExecutionMode {
    /// All connectivity via explicit SynapticEdges + EventRouter.
    Explicit,
    /// Selected local edges replaced by LPU proxy channels.
    Lpu,
    /// Hybrid: a structural subset of edges remains explicit (via EventRouter)
    /// and the complementary subset is replaced by LPU proxy channels.
    /// Both sub-paths read from the identical post-step spike emission frontier,
    /// preserving causal timing integrity.
    Mixed,
}

/// Per-step record from a harness run.
#[derive(Debug, Default, Clone)]
pub struct StepRecord {
    /// Scheduler slot *after* `step()` completes (i.e. the just-completed slot).
    pub slot: u64,
    pub total_spikes: u32,
    pub active_chunks: u32,
    pub dormant_skips: u32,
    /// Events injected into the queue during post-step routing (explicit) or
    /// proxy injections (LPU). Counted after step completes so spike state is current.
    pub events_injected: u32,
}

/// Full run output from the harness.
#[derive(Debug, Default)]
pub struct RunRecord {
    pub mode: Option<ExecutionMode>,
    pub steps: Vec<StepRecord>,
    pub total_units: usize,
    pub num_chunks: usize,
}

impl RunRecord {
    /// Mean firing rate (spikes / unit / step) across the entire run.
    pub fn mean_firing_rate(&self) -> f32 {
        if self.steps.is_empty() || self.total_units == 0 {
            return 0.0;
        }
        let total: u32 = self.steps.iter().map(|s| s.total_spikes).sum();
        total as f32 / (self.steps.len() as f32 * self.total_units as f32)
    }

    /// Total events injected across the run.
    pub fn total_events(&self) -> u64 {
        self.steps.iter().map(|s| s.events_injected as u64).sum()
    }

    /// Mean active chunk count across the run.
    pub fn mean_active_chunks(&self) -> f32 {
        if self.steps.is_empty() {
            return 0.0;
        }
        self.steps
            .iter()
            .map(|s| s.active_chunks as f32)
            .sum::<f32>()
            / self.steps.len() as f32
    }
}

/// Harness configuration for a Phase 2/3 paired experiment.
pub struct HarnessConfig {
    /// Number of excitatory units.
    pub exc_units: usize,
    /// Number of inhibitory units.
    pub inh_units: usize,
    /// Units per chunk (fixed, Phase 1-compatible).
    pub units_per_chunk: usize,
    /// Simulation timestep (ms).
    pub dt: f32,
    /// Number of steps to run.
    pub num_steps: u64,
    /// External input protocol (applied identically to both modes).
    pub input_protocol: InputProtocol,
    /// Router for explicit mode (Mode A). `None` → no local recurrent connections.
    pub router: Option<EventRouter>,
    /// Calibrated LPU aggregation parameters for 2-channel Mode B.
    pub lpu_params: AggregatorParams,
    /// The replaced circuit topology for LPU mode (Mode B).
    ///
    /// LPU mode propagates aggregate spike drive along the same projection graph
    /// as the explicit circuit. `None` → no replaced local connectivity.
    pub replaced_circuit: Option<EIMicrocircuit>,
    /// Pre-computed topology index for O(active_source_chunks) hot-path.
    ///
    /// When `Some`, `run_lpu` and `run_mixed` use this instead of scanning
    /// `replaced_circuit.all_edges()` every step. Build with
    /// `LpuTopologyIndex::build(&circuit, n_chunks)` (2-ch) or
    /// `LpuTopologyIndex::build_with_mode(&circuit, n_chunks, ProxyMode::FourChannel)` (4-ch).
    /// If `None`, the harness falls back to the naïve HashMap path.
    pub lpu_index: Option<LpuTopologyIndex>,
    // ── Phase 3 fields ──────────────────────────────────────────────────────
    /// Proxy mode selector: `TwoChannel` (Phase 2 default) or `FourChannel` (Phase 3).
    ///
    /// When `FourChannel`, `run_lpu` and `run_mixed` dispatch to
    /// `LpuTopologyIndex::step_four_channel` using `richer_params`.
    /// The `lpu_index` must have been built with the matching `ProxyMode`.
    pub proxy_mode: ProxyMode,
    /// Parameters for the Phase 3 four-channel richer proxy.
    ///
    /// Ignored when `proxy_mode == TwoChannel`.
    pub richer_params: RicherProxyParams,
}

/// Build a scheduler pre-populated with chunks for the harness.
///
/// Returns the scheduler and the chunk IDs for E and I populations.
pub fn build_harness_scheduler(
    exc_units: usize,
    inh_units: usize,
    units_per_chunk: usize,
    dt: f32,
) -> (Scheduler, Vec<ChunkId>, Vec<ChunkId>) {
    use crate::core::chunk::ChunkStatus;

    let mut scheduler = Scheduler::new(dt);
    let mut exc_ids = Vec::new();
    let mut inh_ids = Vec::new();
    let mut chunk_id_counter = 0u32;
    let field_decay_tau = 10.0;

    let exc_n_chunks = exc_units.div_ceil(units_per_chunk);
    for i in 0..exc_n_chunks {
        let units = if i < exc_n_chunks - 1 {
            units_per_chunk
        } else {
            let rem = exc_units % units_per_chunk;
            if rem == 0 { units_per_chunk } else { rem }
        };
        let id = ChunkId(chunk_id_counter);
        let mut chunk = Chunk::new(
            id,
            GridCoord {
                x: chunk_id_counter as i32,
                y: 0,
                z: 0,
            },
            units,
            field_decay_tau,
        );
        chunk.status = ChunkStatus::Dormant;
        scheduler.add_chunk(chunk);
        exc_ids.push(id);
        chunk_id_counter += 1;
    }

    let inh_n_chunks = inh_units.div_ceil(units_per_chunk);
    for i in 0..inh_n_chunks {
        let units = if i < inh_n_chunks - 1 {
            units_per_chunk
        } else {
            let rem = inh_units % units_per_chunk;
            if rem == 0 { units_per_chunk } else { rem }
        };
        let id = ChunkId(chunk_id_counter);
        let mut chunk = Chunk::new(
            id,
            GridCoord {
                x: chunk_id_counter as i32,
                y: 1,
                z: 0,
            },
            units,
            field_decay_tau,
        );
        chunk.status = ChunkStatus::Dormant;
        scheduler.add_chunk(chunk);
        inh_ids.push(id);
        chunk_id_counter += 1;
    }

    (scheduler, exc_ids, inh_ids)
}

/// Run Mode A (explicit connectivity).
///
/// # Bookkeeping correctness
/// - `slot`: scheduler `current_slot` after `step()` (already incremented).
/// - `events_injected`: counted *after* routing so it reflects post-step spike state.
pub fn run_explicit(config: &HarnessConfig) -> RunRecord {
    let (mut scheduler, exc_ids, inh_ids) = build_harness_scheduler(
        config.exc_units,
        config.inh_units,
        config.units_per_chunk,
        config.dt,
    );
    let total_units = config.exc_units + config.inh_units;
    let num_chunks = exc_ids.len() + inh_ids.len();
    let mut record = RunRecord {
        mode: Some(ExecutionMode::Explicit),
        total_units,
        num_chunks,
        ..Default::default()
    };

    for _step in 0..config.num_steps {
        // 1. Apply external drive.
        config.input_protocol.inject(&mut scheduler);

        // 2. Advance scheduler → spike_flags updated for this step.
        let step_metrics = scheduler.step();

        // 3. Route post-step spikes via explicit edges (events queued for next slot).
        //    Count *after* routing so events_injected reflects current-step spikes.
        let router = config.router.as_ref();
        if let Some(r) = router {
            r.route_spikes(&mut scheduler, 1.0);
        }

        // 4. Count routed events (must be read from router after routing).
        let events_injected = if let Some(r) = router {
            r.count_injected_events(&scheduler, 1.0)
        } else {
            (0, 0)
        };

        record.steps.push(StepRecord {
            slot: scheduler.current_slot, // incremented inside step()
            total_spikes: step_metrics.total_spikes,
            active_chunks: step_metrics.active_chunk_count,
            dormant_skips: step_metrics.dormant_skip_count,
            events_injected: events_injected.0 + events_injected.1,
        });
    }

    record
}

/// Run Mode B (LPU-replaced connectivity).
///
/// # Propagation correctness
/// Proxy drive is computed from source-chunk spike output (post-step) and
/// injected into **target** chunks following the same projection topology as
/// the replaced explicit circuit. This makes Mode B a compressed representation
/// of the same graph as Mode A, not a decoupled self-recurrent system.
///
/// Drive injection happens *before* the next step so target chunks see the
/// aggregated input on the same delay as explicit edges (delay_slots=1 in both modes).
pub fn run_lpu(config: &mut HarnessConfig, exc_ids: &[ChunkId], inh_ids: &[ChunkId]) -> RunRecord {
    let (mut scheduler, _, _) = build_harness_scheduler(
        config.exc_units,
        config.inh_units,
        config.units_per_chunk,
        config.dt,
    );
    let total_units = config.exc_units + config.inh_units;
    let num_chunks = exc_ids.len() + inh_ids.len();
    let mut record = RunRecord {
        mode: Some(ExecutionMode::Lpu),
        total_units,
        num_chunks,
        ..Default::default()
    };

    for _step in 0..config.num_steps {
        // 1. Apply external drive (identical to explicit mode).
        config.input_protocol.inject(&mut scheduler);

        // 2. Advance scheduler → spike_flags updated.
        let step_metrics = scheduler.step();

        // 3. Propagate LPU drives.
        //    Fast path: pre-computed index iterates only spiking source chunks.
        //    Slow path (fallback): full all_edges() scan + HashMap — kept for
        //    configs that did not pre-build the index.
        let lpu_events: u32 = match &mut config.lpu_index {
            Some(index) => {
                // Dispatch to 2-ch or 4-ch kernel based on proxy_mode.
                match config.proxy_mode {
                    crate::lpu::proxy::ProxyMode::Stateful => index.step_stateful(
                        &mut scheduler,
                        &config.richer_params,
                        config.units_per_chunk,
                    ),
                    crate::lpu::proxy::ProxyMode::FourChannel => {
                        index.step_four_channel(
                            &mut scheduler,
                            &config.richer_params,
                            config.units_per_chunk,
                        )
                    }
                    crate::lpu::proxy::ProxyMode::TwoChannel => {
                        index.step(&mut scheduler, &config.lpu_params, config.units_per_chunk)
                    }
                }
            }
            None => {
                // Naïve fallback: O(num_replaced_edges) + HashMap.
                let mut events: u32 = 0;
                if let Some(circuit) = &config.replaced_circuit {
                    let src_spikes: std::collections::HashMap<ChunkId, f32> = scheduler
                        .chunks
                        .iter()
                        .map(|(&id, c)| (id, c.state.spike_flags.iter().sum::<f32>()))
                        .collect();
                    let mut tgt_drives: std::collections::HashMap<ChunkId, (f32, f32)> =
                        std::collections::HashMap::new();
                    for edge in circuit.all_edges() {
                        let ss = *src_spikes.get(&edge.source_chunk).unwrap_or(&0.0);
                        if ss == 0.0 {
                            continue;
                        }
                        let src_is_exc = edge.source_type == PopulationType::Excitatory;
                        let n = scheduler
                            .chunks
                            .get(&edge.source_chunk)
                            .map(|c| c.state.num_units)
                            .unwrap_or(config.units_per_chunk);
                        let (e, i) = compute_lpu_drive(
                            ss * edge.weight,
                            n,
                            0.0,
                            0.0,
                            config.dt,
                            &config.lpu_params,
                            src_is_exc,
                        );
                        let d = tgt_drives.entry(edge.target_chunk).or_insert((0.0, 0.0));
                        d.0 += e;
                        d.1 += i;
                    }
                    for (tgt_id, (e, i)) in tgt_drives {
                        if e > 0.0 {
                            scheduler.inject_event(crate::core::chunk::DelayedEvent {
                                target_chunk: tgt_id,
                                target_slot: scheduler.current_slot,
                                signal_strength: e,
                            });
                            events += 1;
                        }
                        if i > 0.0 {
                            scheduler.inject_event(crate::core::chunk::DelayedEvent {
                                target_chunk: tgt_id,
                                target_slot: scheduler.current_slot,
                                signal_strength: -i,
                            });
                            events += 1;
                        }
                    }
                }
                events
            }
        };

        record.steps.push(StepRecord {
            slot: scheduler.current_slot,
            total_spikes: step_metrics.total_spikes,
            active_chunks: step_metrics.active_chunk_count,
            dormant_skips: step_metrics.dormant_skip_count,
            events_injected: lpu_events,
        });
    }

    record
}

/// Internal implementation of mixed-mode execution.
///
/// Returns `(record, explicit_events_total, proxy_events_total)` so that
/// `run_mixed` (public, backward-compatible) and `run_mixed_with_retention`
/// can both get the per-path event split without code duplication.
fn run_mixed_impl(
    config: &mut HarnessConfig,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
) -> (RunRecord, u64, u64) {
    let (mut scheduler, _, _) = build_harness_scheduler(
        config.exc_units,
        config.inh_units,
        config.units_per_chunk,
        config.dt,
    );
    let total_units = config.exc_units + config.inh_units;
    let num_chunks = exc_ids.len() + inh_ids.len();
    let mut record = RunRecord {
        mode: Some(ExecutionMode::Mixed),
        total_units,
        num_chunks,
        ..Default::default()
    };
    let mut explicit_total: u64 = 0;
    let mut proxy_total: u64 = 0;

    for _step in 0..config.num_steps {
        // 1. Apply external drive (identical to all other modes).
        config.input_protocol.inject(&mut scheduler);

        // 2. Advance scheduler → spike_flags updated for this step.
        let step_metrics = scheduler.step();

        // ── Both sub-paths below read from the same post-step spike state ──

        // 3a. Explicit sub-path: route kept edges via EventRouter.
        let mut explicit_step: u32 = 0;
        if let Some(r) = config.router.as_ref() {
            r.route_spikes(&mut scheduler, 1.0);
            let counts = r.count_injected_events(&scheduler, 1.0);
            explicit_step = counts.0 + counts.1;
        }
        explicit_total += explicit_step as u64;

        // 3b. LPU sub-path: aggregate replaced edges via proxy.
        //     Fast path: pre-computed index, O(active_source_chunks × out_degree).
        //     Reads from the same spike_flags frontier as 3a.
        let lpu_events = match &mut config.lpu_index {
            Some(index) => match config.proxy_mode {
                crate::lpu::proxy::ProxyMode::Stateful => index.step_stateful(
                    &mut scheduler,
                    &config.richer_params,
                    config.units_per_chunk,
                ),
                crate::lpu::proxy::ProxyMode::FourChannel => index.step_four_channel(
                    &mut scheduler,
                    &config.richer_params,
                    config.units_per_chunk,
                ),
                crate::lpu::proxy::ProxyMode::TwoChannel => {
                    index.step(&mut scheduler, &config.lpu_params, config.units_per_chunk)
                }
            },
            None => {
                // Naïve fallback.
                let mut events: u32 = 0;
                if let Some(circuit) = &config.replaced_circuit {
                    let src_spikes: std::collections::HashMap<ChunkId, f32> = scheduler
                        .chunks
                        .iter()
                        .map(|(&id, c)| (id, c.state.spike_flags.iter().sum::<f32>()))
                        .collect();
                    let mut tgt_drives: std::collections::HashMap<ChunkId, (f32, f32)> =
                        std::collections::HashMap::new();
                    for edge in circuit.all_edges() {
                        let ss = *src_spikes.get(&edge.source_chunk).unwrap_or(&0.0);
                        if ss == 0.0 {
                            continue;
                        }
                        let src_is_exc = edge.source_type == PopulationType::Excitatory;
                        let n = scheduler
                            .chunks
                            .get(&edge.source_chunk)
                            .map(|c| c.state.num_units)
                            .unwrap_or(config.units_per_chunk);
                        let (e, i) = compute_lpu_drive(
                            ss * edge.weight,
                            n,
                            0.0,
                            0.0,
                            config.dt,
                            &config.lpu_params,
                            src_is_exc,
                        );
                        let d = tgt_drives.entry(edge.target_chunk).or_insert((0.0, 0.0));
                        d.0 += e;
                        d.1 += i;
                    }
                    for (tgt_id, (e, i)) in tgt_drives {
                        if e > 0.0 {
                            scheduler.inject_event(crate::core::chunk::DelayedEvent {
                                target_chunk: tgt_id,
                                target_slot: scheduler.current_slot,
                                signal_strength: e,
                            });
                            events += 1;
                        }
                        if i > 0.0 {
                            scheduler.inject_event(crate::core::chunk::DelayedEvent {
                                target_chunk: tgt_id,
                                target_slot: scheduler.current_slot,
                                signal_strength: -i,
                            });
                            events += 1;
                        }
                    }
                }
                events
            }
        };
        proxy_total += lpu_events as u64;

        record.steps.push(StepRecord {
            slot: scheduler.current_slot,
            total_spikes: step_metrics.total_spikes,
            active_chunks: step_metrics.active_chunk_count,
            dormant_skips: step_metrics.dormant_skip_count,
            events_injected: explicit_step + lpu_events,
        });
    }

    (record, explicit_total, proxy_total)
}

/// Run Mode C (hybrid mixed-mode connectivity).
///
/// # Causal timing integrity
/// Both routing paths read from the same post-step spike emission frontier.
/// Both deposit events with identical `delay_slots=1` semantics.
///
/// # Degenerate cases
/// - `router: None, replaced_circuit: Some(_)` → equivalent to `run_lpu`.
/// - `router: Some(_), replaced_circuit: None` → equivalent to `run_explicit`.
pub fn run_mixed(
    config: &mut HarnessConfig,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
) -> RunRecord {
    run_mixed_impl(config, exc_ids, inh_ids).0
}

/// Compute resource savings of LPU vs. explicit for a paired run.
pub struct ResourceDelta {
    pub explicit_events: u64,
    pub lpu_events: u64,
    pub events_saved: i64,
    pub explicit_mean_active: f32,
    pub lpu_mean_active: f32,
}

impl ResourceDelta {
    pub fn compute(explicit: &RunRecord, lpu: &RunRecord) -> Self {
        let exp_ev = explicit.total_events();
        let lpu_ev = lpu.total_events();
        Self {
            explicit_events: exp_ev,
            lpu_events: lpu_ev,
            events_saved: exp_ev as i64 - lpu_ev as i64,
            explicit_mean_active: explicit.mean_active_chunks(),
            lpu_mean_active: lpu.mean_active_chunks(),
        }
    }

    pub fn summary(&self) -> String {
        format!(
            "ResourceDelta: events explicit={} lpu={} saved={} | \
             active_chunks explicit={:.1} lpu={:.1}",
            self.explicit_events,
            self.lpu_events,
            self.events_saved,
            self.explicit_mean_active,
            self.lpu_mean_active,
        )
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Task D: Selective Explicit Retention — mixed-mode runner
// ─────────────────────────────────────────────────────────────────────────────

/// Output of `run_mixed_with_retention`: the run record plus partition statistics.
pub struct RetentionRunResult {
    /// The simulation output (identical format to `run_mixed`).
    pub record: RunRecord,
    /// How many edges were kept explicit vs. replaced by the proxy.
    pub stats: crate::experiment::retention::RetentionStats,
    /// Total scheduler events injected via the explicit (EventRouter) sub-path.
    pub explicit_events: u64,
    /// Total scheduler events injected via the LPU proxy sub-path.
    pub proxy_events: u64,
}

/// Run the mixed-mode harness with a `RetentionPolicy`-driven circuit split.
///
/// This is the **Task D integration point**: it
/// 1. Applies `policy.partition_edges(circuit)` to split edges into kept/replaced.
/// 2. Builds an `EventRouter` from the **kept** edges.
/// 3. Builds an `LpuTopologyIndex` from the **replaced** edges (using `proxy_mode`).
/// 4. Calls `run_mixed` with the fully wired `HarnessConfig`.
///
/// # Arguments
/// - `base_config`: a partially-filled `HarnessConfig` providing `dt`, `num_steps`,
///   `input_protocol`, `lpu_params`, `proxy_mode`, and `richer_params`.
///   `router` and `lpu_index` fields are **overwritten** by this function.
/// - `full_circuit`: the complete `EIMicrocircuit` to partition.
/// - `policy`: the `RetentionPolicy` deciding which edges to keep explicit.
/// - `exc_ids` / `inh_ids`: chunk ID slices for the two populations.
///
/// # Returns
/// A `RetentionRunResult` containing both the `RunRecord` and `RetentionStats`.
pub fn run_mixed_with_retention(
    base_config: &HarnessConfig,
    full_circuit: &crate::connectivity::microcircuit::EIMicrocircuit,
    policy: &crate::experiment::retention::RetentionPolicy,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
) -> RetentionRunResult {
    let n_chunks = exc_ids.len() + inh_ids.len();

    // 1. Partition the full circuit using the retention policy.
    let stats = policy.partition_stats(full_circuit);
    let (kept_edges, _replaced_edges) = policy.partition_edges(full_circuit);

    // 2. Build an EventRouter from the kept (explicit) edges.
    //    We construct a minimal LocalProjection from the kept edge list to feed
    //    EventRouter::from_projections.  The two populations are distinguished
    //    by source_type, matching the existing router API.
    use crate::connectivity::types::{LocalProjection, PopulationType};
    let kept_exc: LocalProjection = LocalProjection {
        label: "kept_exc".to_string(),
        source_type: PopulationType::Excitatory,
        edges: kept_edges
            .iter()
            .filter(|e| e.source_type == PopulationType::Excitatory)
            .cloned()
            .collect(),
    };
    let kept_inh: LocalProjection = LocalProjection {
        label: "kept_inh".to_string(),
        source_type: PopulationType::Inhibitory,
        edges: kept_edges
            .iter()
            .filter(|e| e.source_type == PopulationType::Inhibitory)
            .cloned()
            .collect(),
    };
    let router = crate::connectivity::event_router::EventRouter::from_projections(
        &[&kept_exc, &kept_inh],
        n_chunks,
    );

    // 3. Build a replaced EIMicrocircuit from the replaced edges so we can
    //    construct an LpuTopologyIndex.  We reuse the spec's build path by
    //    directly constructing an EIMicrocircuit with zero edges, then swapping
    //    in the replaced edge lists per projection arm.
    use crate::connectivity::microcircuit::EIMicrocircuit;
    let (_, replaced_edges_vec) = policy.partition_edges(full_circuit);
    let replaced_mc = EIMicrocircuit {
        ee: LocalProjection {
            label: "repl_ee".to_string(),
            source_type: PopulationType::Excitatory,
            edges: replaced_edges_vec
                .iter()
                .filter(|e| e.source_type == PopulationType::Excitatory)
                .cloned()
                .collect(),
        },
        ei: LocalProjection {
            label: "repl_ei".to_string(),
            source_type: PopulationType::Excitatory,
            edges: Vec::new(), // E→I share same source_type; merge below
        },
        ie: LocalProjection {
            label: "repl_ie".to_string(),
            source_type: PopulationType::Inhibitory,
            edges: replaced_edges_vec
                .iter()
                .filter(|e| e.source_type == PopulationType::Inhibitory)
                .cloned()
                .collect(),
        },
        ii: LocalProjection {
            label: "repl_ii".to_string(),
            source_type: PopulationType::Inhibitory,
            edges: Vec::new(), // merged with ie above for now (current simplification)
        },
    };

    let lpu_index = crate::experiment::lpu_index::LpuTopologyIndex::build_with_mode(
        &replaced_mc,
        n_chunks,
        base_config.proxy_mode,
    );

    // 4. Assemble the config and run.
    let mut cfg = HarnessConfig {
        exc_units: base_config.exc_units,
        inh_units: base_config.inh_units,
        units_per_chunk: base_config.units_per_chunk,
        dt: base_config.dt,
        num_steps: base_config.num_steps,
        input_protocol: base_config.input_protocol.clone(),
        router: Some(router),
        lpu_params: base_config.lpu_params.clone(),
        replaced_circuit: Some(replaced_mc),
        lpu_index: Some(lpu_index),
        proxy_mode: base_config.proxy_mode,
        richer_params: base_config.richer_params.clone(),
    };

    let (record, explicit_events, proxy_events) = run_mixed_impl(&mut cfg, exc_ids, inh_ids);

    RetentionRunResult { record, stats, explicit_events, proxy_events }
}
