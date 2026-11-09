//! Phase 3 Richer Proxy Parameters.
//!
//! `RicherProxyParams` holds the independently configurable gain and decay
//! constants for each of the four Phase 3 proxy channels:
//!
//! | Channel    | Biological analogue     | Typical τ  |
//! |------------|-------------------------|-----------|
//! | fast_exc   | AMPA-receptor current   | 2–5 ms    |
//! | slow_exc   | NMDA-receptor current   | 50–100 ms |
//! | fast_inh   | GABA-A receptor current | 5–10 ms   |
//! | slow_inh   | GABA-B receptor current | 50–100 ms |
//!
//! # Scope Restrictions
//! These parameters are **fixed at construction time**. There is no:
//! - Adaptive gain adjustment during simulation.
//! - Online learning of τ values.
//! - Automatic discovery of which motif class is active.
//!
//! Calibration (matching an explicit baseline) is the only supported workflow
//! for setting these values before a Phase 3 experiment.

/// Configuration for the Phase 3 four-channel richer proxy.
///
/// Each field pair (`gain_*` / `tau_*`) governs one of the four channels
/// independently, breaking the symmetry of the Phase 2 proxy where
/// `gain_exc == gain_inh` was enforced after calibration.
#[derive(Debug, Clone)]
pub struct RicherProxyParams {
    // ── Fast Excitatory Channel ────────────────────────────────────────────────
    /// Gain applied to the fast excitatory spike-sum drive.
    pub gain_fast_exc: f32,
    /// Exponential decay time constant for the fast E channel (ms).
    /// The channel decays as `state *= exp(-dt / tau_fast_exc)` per step.
    pub tau_fast_exc: f32,

    // ── Slow Excitatory Channel ────────────────────────────────────────────────
    /// Gain applied to the slow excitatory spike-sum drive.
    pub gain_slow_exc: f32,
    /// Decay time constant for the slow E channel (ms).
    pub tau_slow_exc: f32,

    // ── Fast Inhibitory Channel ────────────────────────────────────────────────
    /// Gain applied to the fast inhibitory spike-sum drive.
    pub gain_fast_inh: f32,
    /// Decay time constant for the fast I channel (ms).
    pub tau_fast_inh: f32,

    // ── Slow Inhibitory Channel ────────────────────────────────────────────────
    /// Gain applied to the slow inhibitory spike-sum drive.
    pub gain_slow_inh: f32,
    /// Decay time constant for the slow I channel (ms).
    pub tau_slow_inh: f32,

    // ── Aggregation mode (shared with Phase 2) ─────────────────────────────────
    /// Use normalized rate (spikes/unit) rather than raw spike count for drive.
    /// Matches the default behaviour of `AggregationMode::NormalizedRate`.
    pub normalize_by_population: bool,
}

impl Default for RicherProxyParams {
    /// Physiologically-informed defaults following the channel table above.
    ///
    /// Initial gains are set to 1.0 (uncalibrated); run the Phase 3 calibration
    /// procedure to fit them against the explicit baseline before comparing.
    fn default() -> Self {
        Self {
            // Fast E: AMPA-like
            gain_fast_exc: 1.0,
            tau_fast_exc: 3.0,
            // Slow E: NMDA-like
            gain_slow_exc: 0.5,
            tau_slow_exc: 80.0,
            // Fast I: GABA-A-like
            gain_fast_inh: 1.0,
            tau_fast_inh: 7.0,
            // Slow I: GABA-B-like
            gain_slow_inh: 0.3,
            tau_slow_inh: 80.0,
            normalize_by_population: true,
        }
    }
}

/// Per-chunk channel state for the four-channel richer proxy.
///
/// This struct holds the *running field values* for each channel.  One instance
/// lives per chunk in the scheduler and is updated each simulation step by
/// `step_richer_lpu_euler`.
///
/// Unlike the stateless Phase 2 proxy (which computes drive purely from the
/// current step's spike count), the richer proxy accumulates short-term history
/// via exponential decay — recovering the `sustained vs. transient` distinction
/// that the 2-channel proxy loses.
#[derive(Debug, Clone, Default)]
pub struct RicherProxyState {
    /// Running field for the fast excitatory channel.
    pub fast_exc: f32,
    /// Running field for the slow excitatory channel.
    pub slow_exc: f32,
    /// Running field for the fast inhibitory channel.
    pub fast_inh: f32,
    /// Running field for the slow inhibitory channel.
    pub slow_inh: f32,
}

impl RicherProxyState {
    /// Net excitatory drive delivered to the chunk this step.
    #[inline]
    pub fn exc_drive(&self) -> f32 {
        self.fast_exc + self.slow_exc
    }

    /// Net inhibitory drive delivered to the chunk this step.
    #[inline]
    pub fn inh_drive(&self) -> f32 {
        self.fast_inh + self.slow_inh
    }
}

/// Update a single chunk's `RicherProxyState` for one simulation step.
///
/// This is the **original combined** form used in unit tests.
/// The hot-path in `LpuTopologyIndex::step_four_channel` should call
/// `decay_richer_state` once per slot and `accumulate_richer_input` per edge
/// to avoid the repeated-decay bug identified in Phase 3 review.
///
/// # Arguments
/// - `state`: mutable proxy state for the target chunk.
/// - `spike_sum`: raw spike count emitted by the relevant source chunk this step.
/// - `src_n_units`: number of units in the source chunk (for normalization).
/// - `src_is_exc`: whether the source population is excitatory.
/// - `edge_weight`: weight of the replaced edge being aggregated.
/// - `dt_ms`: simulation timestep in **milliseconds**.
/// - `params`: calibrated richer proxy parameters.
pub fn update_richer_state(
    state: &mut RicherProxyState,
    spike_sum: f32,
    src_n_units: usize,
    src_is_exc: bool,
    edge_weight: f32,
    dt_ms: f32,
    params: &RicherProxyParams,
) {
    // Normalize drive if requested (mirrors AggregationMode::NormalizedRate).
    let raw_input = if params.normalize_by_population && src_n_units > 0 {
        spike_sum / src_n_units as f32
    } else {
        spike_sum
    } * edge_weight;

    if src_is_exc {
        // Step 1: Decay existing field values.
        let fast_decay = (-dt_ms / params.tau_fast_exc).exp();
        let slow_decay = (-dt_ms / params.tau_slow_exc).exp();
        state.fast_exc *= fast_decay;
        state.slow_exc *= slow_decay;

        // Step 2: Inject new input into both E channels.
        state.fast_exc += raw_input * params.gain_fast_exc;
        state.slow_exc += raw_input * params.gain_slow_exc;
    } else {
        // Inhibitory source: update I channels.
        let fast_decay = (-dt_ms / params.tau_fast_inh).exp();
        let slow_decay = (-dt_ms / params.tau_slow_inh).exp();
        state.fast_inh *= fast_decay;
        state.slow_inh *= slow_decay;

        state.fast_inh += raw_input * params.gain_fast_inh;
        state.slow_inh += raw_input * params.gain_slow_inh;
    }
}

/// **Phase A — Decay only**: apply one full `exp(-dt/τ)` decay tick to all
/// four channels.
///
/// Must be called **once per slot per target chunk**, before any calls to
/// `accumulate_richer_input` for that chunk in the same slot.
///
/// Separating decay from accumulation fixes the indegree-dependent decay bug:
/// a target with N incoming edges should decay exactly once, not N times.
#[inline]
pub fn decay_richer_state(state: &mut RicherProxyState, dt_ms: f32, params: &RicherProxyParams) {
    state.fast_exc *= (-dt_ms / params.tau_fast_exc).exp();
    state.slow_exc *= (-dt_ms / params.tau_slow_exc).exp();
    state.fast_inh *= (-dt_ms / params.tau_fast_inh).exp();
    state.slow_inh *= (-dt_ms / params.tau_slow_inh).exp();
}

/// **Phase B — Accumulate only**: add spike-driven input to the appropriate
/// channel pair **without** applying any decay.
///
/// Call this once per source→target edge within a slot, after the one-time
/// `decay_richer_state` call for that target.
///
/// # Arguments
/// - `state`: mutable proxy state for the target chunk.
/// - `spike_sum`: raw spike count from the source chunk this slot.
/// - `src_n_units`: source population size (for normalization).
/// - `src_is_exc`: whether the source population is excitatory.
/// - `edge_weight`: weight of this replaced edge.
/// - `params`: richer proxy configuration.
#[inline]
pub fn accumulate_richer_input(
    state: &mut RicherProxyState,
    spike_sum: f32,
    src_n_units: usize,
    src_is_exc: bool,
    edge_weight: f32,
    params: &RicherProxyParams,
) {
    let raw_input = if params.normalize_by_population && src_n_units > 0 {
        spike_sum / src_n_units as f32
    } else {
        spike_sum
    } * edge_weight;

    if src_is_exc {
        state.fast_exc += raw_input * params.gain_fast_exc;
        state.slow_exc += raw_input * params.gain_slow_exc;
    } else {
        state.fast_inh += raw_input * params.gain_fast_inh;
        state.slow_inh += raw_input * params.gain_slow_inh;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exc_drive_sums_fast_and_slow() {
        let mut state = RicherProxyState {
            fast_exc: 0.4,
            slow_exc: 0.1,
            fast_inh: 0.2,
            slow_inh: 0.05,
        };
        assert!((state.exc_drive() - 0.5).abs() < 1e-6);
        assert!((state.inh_drive() - 0.25).abs() < 1e-6);

        // Drive should not cross-contaminate channels.
        state.slow_exc = 0.0;
        assert!((state.exc_drive() - 0.4).abs() < 1e-6);
    }

    #[test]
    fn test_state_decays_toward_zero_with_no_input() {
        let params = RicherProxyParams::default();
        // Pre-charge fast_exc channel, then drive with zero spikes.
        let mut state = RicherProxyState {
            fast_exc: 1.0,
            ..Default::default()
        };
        let dt_ms = 1.0_f32;
        // With spike_sum=0 and edge_weight=0, only decay applies.
        update_richer_state(&mut state, 0.0, 100, true, 0.0, dt_ms, &params);
        let expected = (-dt_ms / params.tau_fast_exc).exp();
        assert!(
            (state.fast_exc - expected).abs() < 1e-5,
            "fast_exc should decay to exp(-dt/tau): expected {expected}, got {}",
            state.fast_exc
        );
    }

    #[test]
    fn test_exc_source_does_not_affect_inh_channels() {
        let params = RicherProxyParams::default();
        let mut state = RicherProxyState::default();
        // Inject via an excitatory source.
        update_richer_state(&mut state, 10.0, 100, true, 1.0, 1.0, &params);
        // Inhibitory channels must remain zero.
        assert_eq!(state.fast_inh, 0.0, "fast_inh should be untouched by E source");
        assert_eq!(state.slow_inh, 0.0, "slow_inh should be untouched by E source");
        // Excitatory channels must have received drive.
        assert!(state.fast_exc > 0.0, "fast_exc should have been driven");
        assert!(state.slow_exc > 0.0, "slow_exc should have been driven");
    }

    #[test]
    fn test_inh_source_does_not_affect_exc_channels() {
        let params = RicherProxyParams::default();
        let mut state = RicherProxyState::default();
        // Inject via an inhibitory source.
        update_richer_state(&mut state, 10.0, 100, false, 1.0, 1.0, &params);
        assert_eq!(state.fast_exc, 0.0);
        assert_eq!(state.slow_exc, 0.0);
        assert!(state.fast_inh > 0.0);
        assert!(state.slow_inh > 0.0);
    }

    #[test]
    fn test_slow_channel_decays_slower_than_fast() {
        let params = RicherProxyParams::default();
        // Charge both channels to 1.0, then apply 5 steps of decay (no new input).
        let mut state = RicherProxyState {
            fast_exc: 1.0,
            slow_exc: 1.0,
            ..Default::default()
        };
        let dt_ms = 5.0_f32;
        // Simulate decay-only step.
        update_richer_state(&mut state, 0.0, 1, true, 0.0, dt_ms, &params);
        assert!(
            state.fast_exc < state.slow_exc,
            "fast channel (τ={}) should decay faster than slow (τ={}): fast={} slow={}",
            params.tau_fast_exc,
            params.tau_slow_exc,
            state.fast_exc,
            state.slow_exc
        );
    }

    #[test]
    fn test_normalization_by_population_scales_input() {
        let params = RicherProxyParams {
            normalize_by_population: true,
            ..Default::default()
        };
        let mut state_norm = RicherProxyState::default();
        let mut state_raw = RicherProxyState::default();
        let spike_sum = 50.0_f32;
        let n_units = 100_usize;

        update_richer_state(&mut state_norm, spike_sum, n_units, true, 1.0, 1.0, &params);

        let params_no_norm = RicherProxyParams {
            normalize_by_population: false,
            ..Default::default()
        };
        update_richer_state(&mut state_raw, spike_sum, n_units, true, 1.0, 1.0, &params_no_norm);

        // Normalized drive = (50/100) × gain; raw drive = 50 × gain.
        assert!(
            state_norm.fast_exc < state_raw.fast_exc,
            "normalized fast_exc should be smaller than raw: norm={} raw={}",
            state_norm.fast_exc,
            state_raw.fast_exc
        );
    }
}
