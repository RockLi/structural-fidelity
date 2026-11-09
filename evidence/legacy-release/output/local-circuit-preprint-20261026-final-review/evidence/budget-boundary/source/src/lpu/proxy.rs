//! Phase 3 Proxy Mode Discriminant.
//!
//! Defines the switchable proxy architecture used throughout Phase 3.
//! The `ProxyMode` enum selects between the Phase 2 two-channel stateless proxy
//! and the Phase 3 four-channel fast/slow E/I proxy, allowing rigorous paired
//! comparison on identical benchmarks.
//!
//! # Design Constraints (V1)
//! - No adaptive memory state.
//! - No online learning.
//! - No automatic motif discovery.
//! - E/I gain and decay are separately configurable but fixed at construction.

/// Selects the proxy representation used for LPU-replaced local connectivity.
///
/// Switch from `TwoChannel` (Phase 2 baseline) to `FourChannel` (Phase 3 richer
/// proxy) at the `HarnessConfig` level.  All benchmark and fidelity measurement
/// code remains identical; only the drive computation kernel changes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ProxyMode {
    /// Phase 2 baseline: single E channel + single I channel, stateless.
    ///
    /// Drive is computed by `compute_lpu_drive` in `aggregator.rs` using a
    /// shared `gain_exc` / `gain_inh` parameter pair.
    #[default]
    TwoChannel,

    /// Phase 3 richer proxy: separate fast and slow channels for both E and I.
    ///
    /// Models two distinct time-scale populations:
    /// - `fast_exc`: fast-decaying excitatory drive (AMPA-like τ ≈ 2–5 ms)
    /// - `slow_exc`: slow-decaying excitatory drive (NMDA-like τ ≈ 50–100 ms)
    /// - `fast_inh`: fast-decaying inhibitory drive (GABA-A-like τ ≈ 5 ms)
    /// - `slow_inh`: slow-decaying inhibitory drive (GABA-B-like τ ≈ 50 ms)
    ///
    /// See `RicherProxyParams` and `step_richer_lpu_euler` for the state update.
    FourChannel,

    /// Phase 3 stateful proxy: `FourChannel` plus one population-history trace per chunk.
    ///
    /// Motivation (Conclusion 3): E1 sustained dynamics require population-level temporal
    /// memory beyond what single-step exponential decay provides.  The history trace holds
    /// an α-blended running average of chunk firing rate over ~20 ms.  The drive kernel
    /// consults this trace to scale the fast excitatory channel, bridging the temporal
    /// gap that caps the 4-channel calibrated PSTH-r at ~0.50.
    ///
    /// State layout per chunk: `RicherProxyState` (4ch) + `StatefulProxyTrace` (history).
    ///
    /// # Implementation Status
    /// Scaffold only — kernel integration pending Phase 3 Task 3 approval.
    /// `run_lpu` and `LpuTopologyIndex::step` treat this as an alias for `FourChannel`
    /// until the stateful kernel is wired in.
    Stateful,
}

impl std::fmt::Display for ProxyMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProxyMode::TwoChannel => write!(f, "2ch"),
            ProxyMode::FourChannel => write!(f, "4ch"),
            ProxyMode::Stateful => write!(f, "4ch+trace"),
        }
    }
}

/// Per-chunk population-history trace for `ProxyMode::Stateful`.
///
/// One instance per chunk, updated each step with the chunk's normalised firing rate
/// via an α-blend: `trace = (1 - α) * trace + α * fr_this_step`.
/// The blend coefficient `α = dt_ms / tau_trace_ms` targets a ~20 ms integration window.
///
/// The kernel uses `history_exc` / `history_inh` to scale the fast channel gain,
/// giving the proxy a "memory" of sustained population activity.
#[derive(Debug, Clone, Default)]
pub struct StatefulProxyTrace {
    /// Running α-blended excitatory population FR estimate (spikes / unit / step).
    pub history_exc: f32,
    /// Running α-blended inhibitory population FR estimate (spikes / unit / step).
    pub history_inh: f32,
}

impl StatefulProxyTrace {
    /// Update the trace for one step.
    ///
    /// `fr_exc` / `fr_inh`: normalised firing rates this step (spikes/unit).
    /// `alpha`: blend coefficient (= dt_ms / tau_trace_ms; typical range 0.03–0.10).
    #[inline]
    pub fn update(&mut self, fr_exc: f32, fr_inh: f32, alpha: f32) {
        self.history_exc = (1.0 - alpha) * self.history_exc + alpha * fr_exc;
        self.history_inh = (1.0 - alpha) * self.history_inh + alpha * fr_inh;
    }
}
