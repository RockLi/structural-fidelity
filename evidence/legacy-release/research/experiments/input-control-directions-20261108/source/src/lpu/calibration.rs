//! LPU Calibration Protocol (Task 2.5).
//!
//! Systematically fits `AggregatorParams` (channel gains, time constants) so that
//! the LPU-mode drive approximates the net synaptic input delivered by the
//! explicit baseline under a **reference operating regime**.
//!
//! # Why Calibration Is Required
//! LPU cannot be "dropped in" as a zero-parameter replacement. The proxy channels
//! have different units and magnitudes than summed per-edge conductances. Without
//! calibration, apparent fidelity differences may reflect parameter mismatch
//! rather than architectural limits — confounding Paper 2 conclusions.
//!
//! # Calibration Workflow
//! 1. Run the explicit baseline for `T` steps under the reference drive.
//! 2. Record mean per-chunk `g_local_exc` ± std and mean firing rate.
//! 3. Run LPU mode with a candidate `AggregatorParams` for `T` steps.
//! 4. Compare mean drive and firing rate; adjust gains via bisection.
//! 5. Repeat until gain error < `tolerance`.
//! 6. Freeze calibrated params for all subsequent comparison sweeps.

use crate::lpu::aggregator::{AggregationMode, AggregatorParams};

/// Result of a single calibration probe run.
#[derive(Debug, Clone)]
pub struct CalibrationProbe {
    /// Mean spike rate per unit per step across all chunks.
    pub mean_firing_rate: f32,
    /// Mean `g_local_exc` level across all chunks and units at step T.
    pub mean_g_exc: f32,
    /// Mean `g_local_inh` level across all chunks and units at step T.
    pub mean_g_inh: f32,
}

/// Calibration result: fitted parameters and convergence stats.
#[derive(Debug, Clone)]
pub struct CalibrationResult {
    /// Final calibrated parameters.
    pub params: AggregatorParams,
    /// Firing-rate error at convergence (`lpu_rate - explicit_rate`).
    pub firing_rate_error: f32,
    /// Number of bisection iterations taken.
    pub iterations: u32,
    /// Whether calibration converged within tolerance.
    pub converged: bool,
    /// Mean firing rate of the explicit baseline used as calibration reference.
    /// Stored here so callers can compute `firing_rate_error / explicit_reference_fr`
    /// without re-deriving the reference value from the residual arithmetic.
    pub explicit_reference_fr: f32,
}

impl CalibrationResult {
    pub fn summary(&self) -> String {
        let rel_pct = if self.explicit_reference_fr > 1e-9 {
            (self.firing_rate_error / self.explicit_reference_fr).abs() * 100.0
        } else {
            f32::NAN
        };
        format!(
            "LPU Calibration: converged={} | iters={} | rate_error={:.4} ({:.2}%) | \
             gain_exc={:.4} gain_inh={:.4} mode={:?}",
            self.converged,
            self.iterations,
            self.firing_rate_error,
            rel_pct,
            self.params.gain_exc,
            self.params.gain_inh,
            self.params.mode,
        )
    }

    /// Relative firing-rate error as a percentage of the explicit baseline.
    pub fn fr_error_pct(&self) -> f32 {
        if self.explicit_reference_fr > 1e-9 {
            (self.firing_rate_error / self.explicit_reference_fr).abs() * 100.0
        } else {
            f32::NAN
        }
    }
}

/// Calibrates `AggregatorParams` to match an explicit baseline probe.
///
/// Uses bisection on `gain_exc` and `gain_inh` to match mean firing rate
/// of the LPU mode to the explicit baseline within `tolerance` (relative error).
///
/// # Arguments
/// - `explicit_probe`: statistics from the explicit baseline run.
/// - `lpu_probe_fn`: function that runs LPU mode with given params and returns a probe.
/// - `mode`: aggregation mode to calibrate for.
/// - `tolerance`: acceptable relative firing-rate error (e.g., 0.05 = 5%).
/// - `max_iters`: maximum bisection iterations.
pub fn calibrate<F>(
    explicit_probe: &CalibrationProbe,
    mut lpu_probe_fn: F,
    mode: AggregationMode,
    tolerance: f32,
    max_iters: u32,
) -> CalibrationResult
where
    F: FnMut(&AggregatorParams) -> CalibrationProbe,
{
    // Initial params: unit gains.
    let mut params = AggregatorParams {
        mode,
        gain_exc: 1.0,
        gain_inh: 1.0,
        tau_field: 10.0,
    };

    // Bisection bounds for gain_exc.
    // Upper bound must accommodate large-scale networks (10k+ units) where the
    // required gain to match explicit FR is substantially above 10.  Setting
    // hi=10000 leaves headroom for any scale tested in Paper 2 (up to 500k units).
    let mut lo = 0.0_f32;
    let mut hi = 10000.0_f32;
    let mut firing_rate_error = f32::MAX;
    let mut converged = false;

    for iter in 0..max_iters {
        let lpu_probe = lpu_probe_fn(&params);
        firing_rate_error = lpu_probe.mean_firing_rate - explicit_probe.mean_firing_rate;

        let rel_error = if explicit_probe.mean_firing_rate > 0.0 {
            (firing_rate_error / explicit_probe.mean_firing_rate).abs()
        } else {
            firing_rate_error.abs()
        };

        if rel_error <= tolerance {
            converged = true;
            return CalibrationResult {
                params,
                firing_rate_error,
                iterations: iter + 1,
                converged,
                explicit_reference_fr: explicit_probe.mean_firing_rate,
            };
        }

        // Adjust gain_exc via bisection: increase if LPU fires too little.
        if firing_rate_error < 0.0 {
            // LPU firing rate < explicit: increase gain.
            lo = params.gain_exc;
        } else {
            // LPU firing rate > explicit: decrease gain.
            hi = params.gain_exc;
        }

        if iter == max_iters - 1 {
            // Do not overwrite params with an unprobed midpoint on the final failure step.
            break;
        }

        params.gain_exc = (lo + hi) * 0.5;
        // Mirror inhibitory gain to preserve E/I balance ratio.
        params.gain_inh = params.gain_exc;
    }

    CalibrationResult {
        params,
        firing_rate_error,
        iterations: max_iters,
        converged,
        explicit_reference_fr: explicit_probe.mean_firing_rate,
    }
}

/// Simple recording of per-step firing rates over a run, used to build
/// a `CalibrationProbe` without running a full benchmark.
#[derive(Debug, Default)]
pub struct FiringRateRecorder {
    pub per_step_rates: Vec<f32>,
}

impl FiringRateRecorder {
    pub fn record(&mut self, spike_sum: u32, total_units: usize) {
        let rate = if total_units > 0 {
            spike_sum as f32 / total_units as f32
        } else {
            0.0
        };
        self.per_step_rates.push(rate);
    }

    /// Mean firing rate across all recorded steps.
    pub fn mean_rate(&self) -> f32 {
        if self.per_step_rates.is_empty() {
            return 0.0;
        }
        self.per_step_rates.iter().sum::<f32>() / self.per_step_rates.len() as f32
    }

    /// Convert to a `CalibrationProbe` using only firing-rate info.
    pub fn to_probe(&self, mean_g_exc: f32, mean_g_inh: f32) -> CalibrationProbe {
        CalibrationProbe {
            mean_firing_rate: self.mean_rate(),
            mean_g_exc,
            mean_g_inh,
        }
    }
}
