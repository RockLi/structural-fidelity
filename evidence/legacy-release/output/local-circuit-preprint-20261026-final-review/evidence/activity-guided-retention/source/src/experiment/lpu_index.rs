//! Pre-computed LPU topology index for O(active_sources) hot-path execution.
//!
//! The naive LPU implementation in `run_lpu`/`run_mixed` commits two hot-path
//! errors in every simulation step:
//!
//! 1. `circuit.all_edges()` scans ALL replaced edges regardless of whether their
//!    source chunk spiked, making the inner loop O(num_replaced_edges) per step.
//! 2. A new `HashMap<ChunkId, (f32, f32)>` is allocated per step for target drive
//!    accumulation, adding heap allocation + hash overhead.
//!
//! `LpuTopologyIndex` fixes both:
//!
//! - **By-source grouping** (`Vec<Vec<TargetEntry>>` indexed by ChunkId): only
//!   chunks whose `spike_flags` are non-zero are iterated. Zero-spike steps cost
//!   O(active_source_chunks), not O(num_edges).
//!
//! - **Pre-allocated Vec accumulator** (`Vec<(f32, f32)>` indexed by chunk index):
//!   cleared to zero at the top of each step and reused without heap allocation.
//!
//! This makes the hot-path closer to the O(active_chunks) claim.
//!
//! # Phase 3 Extension
//! `LpuTopologyIndex` now carries an optional `richer_states` field — one
//! `RicherProxyState` per chunk slot — enabling 4-channel proxy execution.
//! When `ProxyMode::TwoChannel` is selected (or the `build()` constructor is used),
//! the richer states are not allocated and the hot-path is identical to Phase 2.

use crate::connectivity::microcircuit::EIMicrocircuit;
use crate::connectivity::types::PopulationType;
use crate::core::chunk::{ChunkId, DelayedEvent};
use crate::core::scheduler::Scheduler;
use crate::lpu::aggregator::{AggregatorParams, compute_lpu_drive};
use crate::lpu::proxy::{ProxyMode, StatefulProxyTrace};
use crate::lpu::proxy_params::{RicherProxyParams, RicherProxyState};

/// One outgoing edge from a source chunk in the LPU index.
#[derive(Debug, Clone)]
struct TargetEntry {
    /// Index into the flat chunk array (== ChunkId.0 for harness-built schedulers).
    target_chunk: ChunkId,
    /// Edge weight.
    weight: f32,
    /// True if source population is excitatory.
    source_is_exc: bool,
}

/// Pre-computed LPU topology for fast hot-path aggregation.
///
/// Build once from an `EIMicrocircuit` and reuse across all simulation steps.
pub struct LpuTopologyIndex {
    /// `by_source[i]` = list of outgoing target entries for ChunkId(i).
    /// Empty vec if chunk `i` has no replaced outgoing edges.
    by_source: Vec<Vec<TargetEntry>>,
    /// Number of source slots allocated (== max_chunk_id + 1).
    n_slots: usize,
    /// Pre-allocated per-step accumulator: (exc_drive, inh_drive) per target chunk.
    /// Reused every step (zero-cleared at start).
    tgt_drives: Vec<(f32, f32)>,
    /// Phase 3: per-chunk running channel state for the 4-channel proxy.
    /// `richer_states[i]` holds the accumulated fast/slow E/I fields for chunk i.
    /// `None` when built with `ProxyMode::TwoChannel` (no allocation overhead).
    richer_states: Option<Vec<RicherProxyState>>,
    /// Phase 3 Task 3 closure: per-chunk population history trace for `ProxyMode::Stateful`.
    /// `None` when built with `TwoChannel` or `FourChannel`.
    stateful_traces: Option<Vec<StatefulProxyTrace>>,
}

impl LpuTopologyIndex {
    /// Build from a replaced `EIMicrocircuit` in two-channel (Phase 2) mode.
    ///
    /// `n_chunks` must equal the total number of chunks in the scheduler so the
    /// `by_source` and `tgt_drives` vectors are sized correctly.
    /// Uses `ProxyMode::TwoChannel` — backward-compatible with all Phase 2 tests.
    pub fn build(circuit: &EIMicrocircuit, n_chunks: usize) -> Self {
        Self::build_with_mode(circuit, n_chunks, ProxyMode::TwoChannel)
    }

    /// Build with an explicit `ProxyMode`.
    ///
    /// - `TwoChannel`: Phase 2 stateless proxy (backward-compatible, no extra alloc).
    /// - `FourChannel`: Phase 3 richer proxy with per-chunk `RicherProxyState` storage.
    pub fn build_with_mode(
        circuit: &EIMicrocircuit,
        n_chunks: usize,
        proxy_mode: ProxyMode,
    ) -> Self {
        let mut by_source: Vec<Vec<TargetEntry>> = vec![Vec::new(); n_chunks];

        for edge in circuit.all_edges() {
            let src_idx = edge.source_chunk.0 as usize;
            if src_idx < n_chunks {
                by_source[src_idx].push(TargetEntry {
                    target_chunk: edge.target_chunk,
                    weight: edge.weight,
                    source_is_exc: edge.source_type == PopulationType::Excitatory,
                });
            }
        }

        let richer_states = match proxy_mode {
            ProxyMode::FourChannel | ProxyMode::Stateful => {
                Some(vec![RicherProxyState::default(); n_chunks])
            }
            ProxyMode::TwoChannel => None,
        };

        let stateful_traces = match proxy_mode {
            ProxyMode::Stateful => Some(vec![StatefulProxyTrace::default(); n_chunks]),
            ProxyMode::TwoChannel | ProxyMode::FourChannel => None,
        };

        Self {
            n_slots: n_chunks,
            tgt_drives: vec![(0.0_f32, 0.0_f32); n_chunks],
            by_source,
            richer_states,
            stateful_traces,
        }
    }

    /// Returns `true` if no replaced edges exist (degenerate index).
    pub fn is_empty(&self) -> bool {
        self.by_source.iter().all(|v| v.is_empty())
    }

    /// Returns which proxy mode this index was built with.
    pub fn proxy_mode(&self) -> ProxyMode {
        if self.stateful_traces.is_some() {
            ProxyMode::Stateful
        } else if self.richer_states.is_some() {
            ProxyMode::FourChannel
        } else {
            ProxyMode::TwoChannel
        }
    }

    /// Execute one LPU aggregation step — **Phase 2 two-channel mode**.
    ///
    /// Backward-compatible signature; uses Phase 2 `AggregatorParams`.
    ///
    /// 1. Reads `spike_flags` for each SOURCE chunk (only iterates occupied slots).
    /// 2. Accumulates weighted drive into pre-allocated `tgt_drives` Vec.
    /// 3. Injects events into the scheduler's event queue.
    /// 4. Returns the count of events enqueued (≤ 2 × active_target_chunks).
    ///
    /// # Hot-path complexity
    /// O(active_source_chunks × avg_out_degree) — NOT O(num_replaced_edges).
    pub fn step(
        &mut self,
        scheduler: &mut Scheduler,
        params: &AggregatorParams,
        units_per_chunk: usize,
    ) -> u32 {
        // Zero-clear accumulator (reuse allocation, no heap cost).
        for d in self.tgt_drives.iter_mut() {
            *d = (0.0, 0.0);
        }

        for (src_idx, targets) in self.by_source.iter().enumerate() {
            if targets.is_empty() {
                continue;
            }
            let src_id = ChunkId(src_idx as u32);
            let spike_sum: f32 = scheduler
                .chunks
                .get(&src_id)
                .map(|c| c.state.spike_flags.iter().sum())
                .unwrap_or(0.0);

            if spike_sum == 0.0 {
                continue; // O(active_chunks) skip
            }

            let src_n_units = scheduler
                .chunks
                .get(&src_id)
                .map(|c| c.state.num_units)
                .unwrap_or(units_per_chunk);

            for tgt in targets {
                let (exc_drive, inh_drive) = compute_lpu_drive(
                    spike_sum * tgt.weight,
                    src_n_units,
                    0.0,
                    0.0,
                    scheduler.dt,
                    params,
                    tgt.source_is_exc,
                );
                let t = tgt.target_chunk.0 as usize;
                if t < self.n_slots {
                    self.tgt_drives[t].0 += exc_drive;
                    self.tgt_drives[t].1 += inh_drive;
                }
            }
        }

        // Inject accumulated drives: Vec-indexed, no HashMap lookup.
        self.inject_drives(scheduler)
    }

    /// Execute one aggregation step using the Phase 3 **four-channel** richer proxy.
    ///
    /// # Correct three-phase algorithm
    ///
    /// **Phase A — Decay (once per slot per target)**
    /// Apply `exp(-dt/τ)` to every occupied target chunk's channel state.
    /// This must happen exactly once, before any source edge is processed.
    ///
    /// **Phase B — Accumulate (once per source→target edge)**
    /// For each spiking source, add the normalized spike drive to the appropriate
    /// channel pair (E or I) in the target's state — no decay here.
    ///
    /// **Phase C — Inject (once per target with non-zero state)**
    /// Inject the **full, current** `exc_drive()` / `inh_drive()` into the scheduler.
    /// Not a delta: the state already encodes the complete channel history, so the
    /// residual from previous slots is delivered even when there is no new input.
    ///
    /// This three-phase structure is what makes the proxy "stateful" — the slow
    /// NMDA-like channel continues to drive the network for tens of ms after a
    /// burst, independently of whether the source is currently spiking.
    ///
    /// Returns 0 and is a no-op if this index was built with `ProxyMode::TwoChannel`.
    pub fn step_four_channel(
        &mut self,
        scheduler: &mut Scheduler,
        richer_params: &RicherProxyParams,
        units_per_chunk: usize,
    ) -> u32 {
        let states = match self.richer_states.as_mut() {
            Some(s) => s,
            None => return 0, // guard: not built with FourChannel mode
        };

        let dt_ms = scheduler.dt;

        // ── Phase A: Decay every tracked target state exactly once ───────────
        // Iterating all n_slots is O(n_chunks); for large networks with sparse
        // connections, only occupied chunks have non-zero state so the cost is
        // proportional to the active target set.
        for state in states.iter_mut() {
            crate::lpu::proxy_params::decay_richer_state(state, dt_ms, richer_params);
        }

        // ── Phase B: Accumulate spike inputs — no decay ───────────────────────
        for (src_idx, targets) in self.by_source.iter().enumerate() {
            if targets.is_empty() {
                continue;
            }
            let src_id = ChunkId(src_idx as u32);
            let spike_sum: f32 = scheduler
                .chunks
                .get(&src_id)
                .map(|c| c.state.spike_flags.iter().sum())
                .unwrap_or(0.0);

            if spike_sum == 0.0 {
                continue; // skip zero-spike sources — no input to accumulate
            }

            let src_n_units = scheduler
                .chunks
                .get(&src_id)
                .map(|c| c.state.num_units)
                .unwrap_or(units_per_chunk);

            for tgt in targets {
                let tgt_idx = tgt.target_chunk.0 as usize;
                if tgt_idx >= self.n_slots {
                    continue;
                }
                crate::lpu::proxy_params::accumulate_richer_input(
                    &mut states[tgt_idx],
                    spike_sum,
                    src_n_units,
                    tgt.source_is_exc,
                    tgt.weight,
                    richer_params,
                );
            }
        }

        // ── Phase C: Inject the full current state into the scheduler ─────────
        // We inject the full exc_drive() / inh_drive() — not a delta.
        // This delivers the residual (slow-channel) history even on zero-spike slots.
        let mut events: u32 = 0;
        let current_slot = scheduler.current_slot;
        for (tgt_idx, state) in states.iter().enumerate() {
            let exc = state.exc_drive();
            let inh = state.inh_drive();
            if exc > 0.0 {
                scheduler.inject_event(DelayedEvent {
                    target_chunk: ChunkId(tgt_idx as u32),
                    target_slot: current_slot,
                    signal_strength: exc,
                });
                events += 1;
            }
            if inh > 0.0 {
                scheduler.inject_event(DelayedEvent {
                    target_chunk: ChunkId(tgt_idx as u32),
                    target_slot: current_slot,
                    signal_strength: -inh,
                });
                events += 1;
            }
        }
        events
    }

    /// Execute one aggregation step using the Phase 3 **stateful** proxy (`4ch+trace`).
    ///
    /// Combines:
    /// 1. 4-channel fast/slow E/I exponential filtering (`RicherProxyState`) with
    ///    unit-gain innovation `(1 - exp(-dt/τ))` to prevent double temporal integration.
    /// 2. Per-chunk 20 ms running population-history trace (`StatefulProxyTrace`) that
    ///    provides homeostatic E/I gain regulation and sustained temporal memory.
    /// 3. Causal 1-slot propagation delay (`target_slot = current_slot + 1`) matching
    ///    `EventRouter::route_spikes` (`delay_slots = 1`).
    pub fn step_stateful(
        &mut self,
        scheduler: &mut Scheduler,
        richer_params: &RicherProxyParams,
        _units_per_chunk: usize,
    ) -> u32 {
        let (states, traces) = match (self.richer_states.as_mut(), self.stateful_traces.as_mut()) {
            (Some(s), Some(t)) => (s, t),
            _ => return 0,
        };

        let dt_ms = scheduler.dt;
        let d_fe = (-dt_ms / richer_params.tau_fast_exc.max(0.1)).exp();
        let d_se = (-dt_ms / richer_params.tau_slow_exc.max(0.1)).exp();
        let d_fi = (-dt_ms / richer_params.tau_fast_inh.max(0.1)).exp();
        let d_si = (-dt_ms / richer_params.tau_slow_inh.max(0.1)).exp();
        let alpha_trace = (dt_ms / 20.0).clamp(0.005, 0.25);

        for d in self.tgt_drives.iter_mut() {
            *d = (0.0, 0.0);
        }

        // Phase A: Decay 4-channel state once per target chunk.
        for state in states.iter_mut() {
            state.fast_exc *= d_fe;
            state.slow_exc *= d_se;
            state.fast_inh *= d_fi;
            state.slow_inh *= d_si;
        }

        // Phase B: O(active_chunks) accumulation from spiking source chunks.
        for (src_idx, targets) in self.by_source.iter().enumerate() {
            if targets.is_empty() {
                continue;
            }
            let src_id = ChunkId(src_idx as u32);
            let spike_sum: f32 = scheduler
                .chunks
                .get(&src_id)
                .map(|c| c.state.spike_flags.iter().sum())
                .unwrap_or(0.0);

            if spike_sum == 0.0 {
                continue;
            }

            for tgt in targets {
                let tgt_idx = tgt.target_chunk.0 as usize;
                if tgt_idx >= self.n_slots {
                    continue;
                }
                let raw_syn = spike_sum * tgt.weight;
                if tgt.source_is_exc {
                    self.tgt_drives[tgt_idx].0 += raw_syn;
                    states[tgt_idx].fast_exc += (1.0 - d_fe) * raw_syn;
                    states[tgt_idx].slow_exc += (1.0 - d_se) * raw_syn;
                } else {
                    self.tgt_drives[tgt_idx].1 += raw_syn;
                    states[tgt_idx].fast_inh += (1.0 - d_fi) * raw_syn;
                    states[tgt_idx].slow_inh += (1.0 - d_si) * raw_syn;
                }
            }
        }

        // Phase C: Update 20ms population history trace and inject charge-conserving
        // 4-channel + trace modulated drive at causal 1-slot delay (`current_slot + 1`).
        let gfe = richer_params.gain_fast_exc.max(0.05);
        let gfi = richer_params.gain_fast_inh.max(0.05);
        let kappa_exc = (0.955 + 0.015 * gfe).clamp(0.90, 1.08);
        let kappa_inh = (0.985 + 0.045 * gfi).clamp(0.90, 1.08);

        let mut events: u32 = 0;
        let target_slot = scheduler.current_slot + 1;

        for tgt_idx in 0..self.n_slots {
            let (raw_exc, raw_inh) = self.tgt_drives[tgt_idx];
            traces[tgt_idx].update(raw_exc, raw_inh, alpha_trace);

            let state = &states[tgt_idx];
            let trace = &traces[tgt_idx];

            if raw_exc > 0.0 {
                // Dimensionless fast-vs-trace contrast: zero steady-state bias, damps
                // high-frequency refractory overshoot while preserving slow/gamma envelopes.
                let denom_e = state.fast_exc + trace.history_exc + 1e-3;
                let mod_e = (state.fast_exc - trace.history_exc) / denom_e;
                let slow_ratio_e =
                    (state.slow_exc / (trace.history_exc + 1e-3)).clamp(0.0, 1.5);
                let filter_gain_e = 1.0 - 0.03 * mod_e + 0.01 * (slow_ratio_e - 0.5);
                let exc_drive = kappa_exc * filter_gain_e * raw_exc;
                if exc_drive > 0.0 {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: ChunkId(tgt_idx as u32),
                        target_slot,
                        signal_strength: exc_drive,
                    });
                    events += 1;
                }
            }

            if raw_inh > 0.0 {
                let denom_i = state.fast_inh + trace.history_inh + 1e-3;
                let mod_i = (state.fast_inh - trace.history_inh) / denom_i;
                let slow_ratio_i =
                    (state.slow_inh / (trace.history_inh + 1e-3)).clamp(0.0, 1.5);
                let filter_gain_i = 1.0 - 0.03 * mod_i + 0.01 * (slow_ratio_i - 0.5);
                let inh_drive = kappa_inh * filter_gain_i * raw_inh;
                if inh_drive > 0.0 {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: ChunkId(tgt_idx as u32),
                        target_slot,
                        signal_strength: -inh_drive,
                    });
                    events += 1;
                }
            }
        }

        events
    }

    // Additive raw-output control; other calculations intentionally retained.
    pub fn step_raw_sum_control(
        &mut self,
        scheduler: &mut Scheduler,
        richer_params: &RicherProxyParams,
        _units_per_chunk: usize,
    ) -> u32 {
        let (states, traces) = match (self.richer_states.as_mut(), self.stateful_traces.as_mut()) {
            (Some(s), Some(t)) => (s, t),
            _ => return 0,
        };

        let dt_ms = scheduler.dt;
        let d_fe = (-dt_ms / richer_params.tau_fast_exc.max(0.1)).exp();
        let d_se = (-dt_ms / richer_params.tau_slow_exc.max(0.1)).exp();
        let d_fi = (-dt_ms / richer_params.tau_fast_inh.max(0.1)).exp();
        let d_si = (-dt_ms / richer_params.tau_slow_inh.max(0.1)).exp();
        let alpha_trace = (dt_ms / 20.0).clamp(0.005, 0.25);

        for d in self.tgt_drives.iter_mut() {
            *d = (0.0, 0.0);
        }

        // Phase A: Decay 4-channel state once per target chunk.
        for state in states.iter_mut() {
            state.fast_exc *= d_fe;
            state.slow_exc *= d_se;
            state.fast_inh *= d_fi;
            state.slow_inh *= d_si;
        }

        // Phase B: O(active_chunks) accumulation from spiking source chunks.
        for (src_idx, targets) in self.by_source.iter().enumerate() {
            if targets.is_empty() {
                continue;
            }
            let src_id = ChunkId(src_idx as u32);
            let spike_sum: f32 = scheduler
                .chunks
                .get(&src_id)
                .map(|c| c.state.spike_flags.iter().sum())
                .unwrap_or(0.0);

            if spike_sum == 0.0 {
                continue;
            }

            for tgt in targets {
                let tgt_idx = tgt.target_chunk.0 as usize;
                if tgt_idx >= self.n_slots {
                    continue;
                }
                let raw_syn = spike_sum * tgt.weight;
                if tgt.source_is_exc {
                    self.tgt_drives[tgt_idx].0 += raw_syn;
                    states[tgt_idx].fast_exc += (1.0 - d_fe) * raw_syn;
                    states[tgt_idx].slow_exc += (1.0 - d_se) * raw_syn;
                } else {
                    self.tgt_drives[tgt_idx].1 += raw_syn;
                    states[tgt_idx].fast_inh += (1.0 - d_fi) * raw_syn;
                    states[tgt_idx].slow_inh += (1.0 - d_si) * raw_syn;
                }
            }
        }

        // Phase C: Update 20ms population history trace and inject charge-conserving
        // 4-channel + trace modulated drive at causal 1-slot delay (`current_slot + 1`).
        let gfe = richer_params.gain_fast_exc.max(0.05);
        let gfi = richer_params.gain_fast_inh.max(0.05);
        let kappa_exc = (0.955 + 0.015 * gfe).clamp(0.90, 1.08);
        let kappa_inh = (0.985 + 0.045 * gfi).clamp(0.90, 1.08);

        let mut events: u32 = 0;
        let target_slot = scheduler.current_slot + 1;

        for tgt_idx in 0..self.n_slots {
            let (raw_exc, raw_inh) = self.tgt_drives[tgt_idx];
            traces[tgt_idx].update(raw_exc, raw_inh, alpha_trace);

            let state = &states[tgt_idx];
            let trace = &traces[tgt_idx];

            if raw_exc > 0.0 {
                // Dimensionless fast-vs-trace contrast: zero steady-state bias, damps
                // high-frequency refractory overshoot while preserving slow/gamma envelopes.
                let denom_e = state.fast_exc + trace.history_exc + 1e-3;
                let mod_e = (state.fast_exc - trace.history_exc) / denom_e;
                let slow_ratio_e =
                    (state.slow_exc / (trace.history_exc + 1e-3)).clamp(0.0, 1.5);
                let filter_gain_e = 1.0 - 0.03 * mod_e + 0.01 * (slow_ratio_e - 0.5);
                let exc_drive = raw_exc;
                if exc_drive > 0.0 {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: ChunkId(tgt_idx as u32),
                        target_slot,
                        signal_strength: exc_drive,
                    });
                    events += 1;
                }
            }

            if raw_inh > 0.0 {
                let denom_i = state.fast_inh + trace.history_inh + 1e-3;
                let mod_i = (state.fast_inh - trace.history_inh) / denom_i;
                let slow_ratio_i =
                    (state.slow_inh / (trace.history_inh + 1e-3)).clamp(0.0, 1.5);
                let filter_gain_i = 1.0 - 0.03 * mod_i + 0.01 * (slow_ratio_i - 0.5);
                let inh_drive = raw_inh;
                if inh_drive > 0.0 {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: ChunkId(tgt_idx as u32),
                        target_slot,
                        signal_strength: -inh_drive,
                    });
                    events += 1;
                }
            }
        }

        events
    }

    /// Inject the contents of `self.tgt_drives` into the scheduler event queue.
    ///
    /// Shared by both `step` (2-ch) and `step_four_channel` (4-ch) to avoid
    /// code repetition. Returns the total event count injected.
    fn inject_drives(&mut self, scheduler: &mut Scheduler) -> u32 {
        let mut events: u32 = 0;
        let current_slot = scheduler.current_slot;
        for (idx, &(exc_drive, inh_drive)) in self.tgt_drives.iter().enumerate() {
            if exc_drive > 0.0 {
                scheduler.inject_event(DelayedEvent {
                    target_chunk: ChunkId(idx as u32),
                    target_slot: current_slot,
                    signal_strength: exc_drive,
                });
                events += 1;
            }
            if inh_drive > 0.0 {
                scheduler.inject_event(DelayedEvent {
                    target_chunk: ChunkId(idx as u32),
                    target_slot: current_slot,
                    signal_strength: -inh_drive,
                });
                events += 1;
            }
        }
        events
    }
}
