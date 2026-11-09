//! Local Field Aggregator: aggregation rule mapping explicit spike events
//! into LPU channel drive values.
//!
//! # The Core Aggregation Question
//! When LPU mode replaces explicit micro-edges, each incoming spike event is
//! no longer individually routed to a target unit via a `SynapticEdge`. Instead,
//! the aggregate local activity of the source population is integrated into a
//! low-dimensional field that drives the LPU channels of the target chunk.
//!
//! The aggregation rule answers:
//! > How do explicit local spike events map to `g_local_exc` / `g_local_inh` channel drive?
//!
//! # Aggregation Choices
//! Three strategies are supported, controlled by [`AggregationMode`]:
//!
//! 1. **FiringCount** (default): drive = sum of spikes in source chunk × weight.
//!    Simple, interpretable, directly analogous to a summed EPSC/IPSC.
//!
//! 2. **NormalizedRate**: drive = (spike_count / num_units) × weight.
//!    Represents population firing rate; scale-invariant across chunk sizes.
//!    Preferred when comparing microcircuits of different sizes.
//!
//! 3. **ExponentialDecayField**: drive accumulates with exponential decay.
//!    Models a leaky integrator field (conductance with time constant `tau_field`).
//!    Closest to a continuous local field potential approximation.
//!
//! All three strategies are *deterministic* and *stateless between slots*
//! except for ExponentialDecayField which requires state in `ChunkContext`.

/// Aggregation strategy for mapping spike output to LPU channel drive.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AggregationMode {
    /// Drive = raw spike count × weight.
    FiringCount,
    /// Drive = (spike_count / num_units) × weight (population rate).
    NormalizedRate,
    /// Drive accumulates via exponential decay (requires ChunkContext fields).
    ExponentialDecayField,
}

impl Default for AggregationMode {
    fn default() -> Self {
        Self::NormalizedRate
    }
}

/// Parameters controlling LPU channel aggregation.
///
/// Calibrated by [`LpuCalibrator`] against the explicit baseline to ensure
/// that the LPU drive approximates the net synaptic input seen by the
/// explicit model under the reference operating regime.
#[derive(Debug, Clone)]
pub struct AggregatorParams {
    /// Aggregation strategy.
    pub mode: AggregationMode,
    /// Excitatory channel gain (scales the E drive into `g_local_exc`).
    pub gain_exc: f32,
    /// Inhibitory channel gain (scales the I drive into `g_local_inh`).
    pub gain_inh: f32,
    /// Time constant for ExponentialDecayField mode (ms / slots).
    pub tau_field: f32,
}

impl Default for AggregatorParams {
    fn default() -> Self {
        Self {
            mode: AggregationMode::NormalizedRate,
            gain_exc: 1.0,
            gain_inh: 1.0,
            tau_field: 10.0,
        }
    }
}

/// Computes the LPU drive from a single chunk's spike output.
///
/// Returns `(exc_drive, inh_drive)` to be added to the target chunk's
/// `g_local_exc` and `g_local_inh` fields respectively.
///
/// # Arguments
/// - `spike_sum`: sum of spike_flags for the source chunk this step.
/// - `num_units`: number of units in the source chunk (for normalization).
/// - `current_exc_field`: current `local_exc_field` in ChunkContext (used in decay mode).
/// - `current_inh_field`: current `local_inh_field` in ChunkContext (used in decay mode).
/// - `dt`: simulation timestep (ms).
/// - `params`: calibrated aggregation parameters.
/// - `source_is_excitatory`: true for E population, false for I.
#[allow(clippy::too_many_arguments)]
pub fn compute_lpu_drive(
    spike_sum: f32,
    num_units: usize,
    current_exc_field: f32,
    current_inh_field: f32,
    dt: f32,
    params: &AggregatorParams,
    source_is_excitatory: bool,
) -> (f32, f32) {
    let raw_drive = match params.mode {
        AggregationMode::FiringCount => spike_sum,
        AggregationMode::NormalizedRate => {
            if num_units > 0 {
                spike_sum / num_units as f32
            } else {
                0.0
            }
        }
        AggregationMode::ExponentialDecayField => {
            // In decay mode the field itself is updated externally in ChunkContext;
            // here we return the current accumulated field as the drive.
            if source_is_excitatory {
                return (current_exc_field * params.gain_exc, 0.0);
            } else {
                return (0.0, current_inh_field * params.gain_inh);
            }
        }
    };

    let _ = (current_exc_field, current_inh_field, dt);

    if source_is_excitatory {
        (raw_drive * params.gain_exc, 0.0)
    } else {
        (0.0, raw_drive * params.gain_inh)
    }
}
