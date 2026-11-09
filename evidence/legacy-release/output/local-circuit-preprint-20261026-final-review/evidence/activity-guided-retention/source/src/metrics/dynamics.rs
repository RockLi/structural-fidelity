//! Dynamics-preservation metrics for Phase 2 Paper 2 comparison (Task 4).
//!
//! Implements the **Core Fidelity Set** that must be completed for Paper 2,
//! plus the **Extended Fidelity Set** as optional deep-dive metrics.
//!
//! # Core Fidelity Set (Must Complete)
//! 1. Mean firing-rate deviation
//! 2. Spike-count deviation
//! 3. Local population activity trajectory similarity (correlation)
//! 4. Propagation / recovery timing deviation  ← first-crossing at 50% peak
//! 5. Spectral peak (dominant frequency) deviation
//!
//! # Extended Fidelity Set (Bonus)
//! - PSD slope (power spectral density shape)
//! - Cross-correlation structure
//! - E/I balance trajectory
//! - Burst statistics

use crate::experiment::harness::RunRecord;

/// Core fidelity metrics comparing an LPU run against an explicit baseline.
#[derive(Debug, Clone)]
pub struct DynamicsFidelity {
    // ── Core Set ──────────────────────────────────────────────────────────
    /// Absolute difference in mean firing rate (spikes/unit/step).
    pub firing_rate_deviation: f32,
    /// Relative firing-rate error (fraction of explicit rate).
    pub firing_rate_relative_error: f32,
    /// Absolute spike-count difference summed over all steps.
    pub spike_count_deviation: i64,
    /// Pearson correlation of per-step spike trajectories.
    pub trajectory_correlation: f32,
    /// Propagation / recovery timing deviation:
    /// difference in first-crossing slot (at 50% of peak rate)
    /// between explicit and LPU trajectories.
    /// Positive = LPU onset is later; negative = earlier.
    /// `None` if neither trajectory reaches a clear peak.
    pub timing_deviation_slots: Option<i64>,
    /// Dominant frequency deviation (Hz) if >0 detected, else None.
    pub spectral_peak_deviation_hz: Option<f32>,

    // ── Extended Set ──────────────────────────────────────────────────────
    /// Mean consecutive inter-step spike ratio (burst proxy).
    pub burst_ratio: Option<f32>,
}

impl DynamicsFidelity {
    /// Compute core fidelity metrics from a paired explicit/LPU run record.
    pub fn compute(explicit: &RunRecord, lpu: &RunRecord, dt_ms: f32) -> Self {
        let exp_rate = explicit.mean_firing_rate();
        let lpu_rate = lpu.mean_firing_rate();

        let firing_rate_deviation = (lpu_rate - exp_rate).abs();
        let firing_rate_relative_error = if exp_rate > 0.0 {
            firing_rate_deviation / exp_rate
        } else {
            0.0
        };

        let exp_spikes: i64 = explicit.steps.iter().map(|s| s.total_spikes as i64).sum();
        let lpu_spikes: i64 = lpu.steps.iter().map(|s| s.total_spikes as i64).sum();
        let spike_count_deviation = (lpu_spikes - exp_spikes).abs();

        // Pearson correlation of per-step trajectories.
        let trajectory_correlation = pearson_correlation(explicit, lpu);

        // Propagation / recovery timing deviation:
        // first slot where trajectory crosses 50% of its peak.
        let timing_deviation_slots = {
            let exp_cross = first_crossing_slot_at_half_peak(explicit);
            let lpu_cross = first_crossing_slot_at_half_peak(lpu);
            match (exp_cross, lpu_cross) {
                (Some(e), Some(l)) => Some(l as i64 - e as i64),
                _ => None,
            }
        };

        // Dominant frequency via zero-crossing rate (simple proxy, no FFT dependency).
        let spectral_peak_deviation_hz = {
            let exp_peak = dominant_frequency_zcr(explicit, dt_ms);
            let lpu_peak = dominant_frequency_zcr(lpu, dt_ms);
            match (exp_peak, lpu_peak) {
                (Some(e), Some(l)) => Some((e - l).abs()),
                _ => None,
            }
        };

        let burst_ratio_val = Some(burst_ratio(explicit, lpu));

        Self {
            firing_rate_deviation,
            firing_rate_relative_error,
            spike_count_deviation,
            trajectory_correlation,
            timing_deviation_slots,
            spectral_peak_deviation_hz,
            burst_ratio: burst_ratio_val,
        }
    }

    /// One-line summary for reporting.
    pub fn summary(&self) -> String {
        format!(
            "DynamicsFidelity: rate_dev={:.4} ({:.1}%) | spike_dev={} | \
             traj_corr={:.4} | timing_dev={} | spectral_dev={} | burst_ratio={}",
            self.firing_rate_deviation,
            self.firing_rate_relative_error * 100.0,
            self.spike_count_deviation,
            self.trajectory_correlation,
            self.timing_deviation_slots
                .map(|v| format!("{:+} slots", v))
                .unwrap_or_else(|| "N/A".to_string()),
            self.spectral_peak_deviation_hz
                .map(|v| format!("{:.2} Hz", v))
                .unwrap_or_else(|| "N/A".to_string()),
            self.burst_ratio
                .map(|v| format!("{:.4}", v))
                .unwrap_or_else(|| "N/A".to_string()),
        )
    }

    /// Returns `true` if all core metrics pass the Paper 2 acceptance threshold.
    ///
    /// Thresholds:
    /// - Firing-rate relative error < 10%
    /// - Trajectory correlation > 0.9
    /// - Timing deviation |Δslots| ≤ 5 (or not computable)
    pub fn passes_core_threshold(&self) -> bool {
        let timing_ok = self
            .timing_deviation_slots
            .map(|d| d.abs() <= 5)
            .unwrap_or(true);
        self.firing_rate_relative_error < 0.10 && self.trajectory_correlation > 0.90 && timing_ok
    }
}

// ── Helper: Pearson correlation ───────────────────────────────────────────

fn pearson_correlation(a: &RunRecord, b: &RunRecord) -> f32 {
    let n = a.steps.len().min(b.steps.len());
    if n == 0 {
        return 0.0;
    }

    let xa: Vec<f32> = a.steps[..n].iter().map(|s| s.total_spikes as f32).collect();
    let xb: Vec<f32> = b.steps[..n].iter().map(|s| s.total_spikes as f32).collect();

    let mean_a = xa.iter().sum::<f32>() / n as f32;
    let mean_b = xb.iter().sum::<f32>() / n as f32;

    let cov: f32 = xa
        .iter()
        .zip(xb.iter())
        .map(|(a, b)| (a - mean_a) * (b - mean_b))
        .sum::<f32>()
        / n as f32;

    let std_a = (xa.iter().map(|a| (a - mean_a).powi(2)).sum::<f32>() / n as f32).sqrt();
    let std_b = (xb.iter().map(|b| (b - mean_b).powi(2)).sum::<f32>() / n as f32).sqrt();

    if std_a > 0.0 && std_b > 0.0 {
        cov / (std_a * std_b)
    } else {
        0.0
    }
}

// ── Helper: First crossing at 50% of peak ────────────────────────────────

/// Returns the step index where the trajectory first reaches ≥ 50% of its peak.
/// Returns `None` if the trajectory is flat (peak == 0).
fn first_crossing_slot_at_half_peak(record: &RunRecord) -> Option<usize> {
    let spikes: Vec<f32> = record.steps.iter().map(|s| s.total_spikes as f32).collect();
    let peak = spikes.iter().cloned().fold(0.0_f32, f32::max);
    if peak == 0.0 {
        return None;
    }
    let threshold = peak * 0.5;
    spikes.iter().position(|&v| v >= threshold)
}

// ── Helper: Zero-crossing rate as dominant frequency proxy ────────────────

/// Estimate dominant oscillation frequency via zero-crossing rate.
/// Returns `None` if the trajectory is flat (no oscillation detected).
fn dominant_frequency_zcr(record: &RunRecord, dt_ms: f32) -> Option<f32> {
    if record.steps.len() < 4 {
        return None;
    }

    let spikes: Vec<f32> = record.steps.iter().map(|s| s.total_spikes as f32).collect();
    let mean = spikes.iter().sum::<f32>() / spikes.len() as f32;

    let crossings = spikes
        .windows(2)
        .filter(|w| (w[0] - mean).signum() != (w[1] - mean).signum())
        .count();

    if crossings == 0 {
        return None;
    }

    // Half-cycle per crossing → freq = crossings / (2 × T).
    let duration_ms = record.steps.len() as f32 * dt_ms;
    let freq_hz = (crossings as f32 / (2.0 * duration_ms)) * 1000.0;
    Some(freq_hz)
}

// ── Helper: Burst ratio ───────────────────────────────────────────────────

/// Fraction of steps where both the explicit and LPU runs had > 0 spikes.
fn burst_ratio(explicit: &RunRecord, lpu: &RunRecord) -> f32 {
    let n = explicit.steps.len().min(lpu.steps.len());
    if n == 0 {
        return 0.0;
    }
    let both_active = explicit.steps[..n]
        .iter()
        .zip(lpu.steps[..n].iter())
        .filter(|(e, l)| e.total_spikes > 0 && l.total_spikes > 0)
        .count();
    both_active as f32 / n as f32
}
