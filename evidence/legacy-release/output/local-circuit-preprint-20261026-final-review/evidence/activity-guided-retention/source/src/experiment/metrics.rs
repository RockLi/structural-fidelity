use crate::experiment::harness::RunRecord;

/// Extracted population dynamics signatures of a single execution record.
///
/// # Units convention
/// All methods accept `dt_s: f32`, the simulation timestep in **seconds**
/// (matching `HarnessConfig::dt`, e.g. `0.001` for a 1 ms step).  Internally
/// the module converts to Hz and ms as needed.  Passing `dt_s = 0.001` gives
/// the same results as the previous `dt = 1.0` (ms) convention — but is now
/// safe to derive straight from the config without a manual unit conversion.
#[derive(Debug, Clone, Default)]
pub struct PopulationDynamics {
    pub mean_fr_hz: f32,
    pub cv_pop: f32,
    pub peak_freq_hz: f32,
    pub peak_power: f32,
    pub max_fr_hz: f32,
    pub t_peak_ms: f32,
    pub rise_time_10_90_ms: f32,
    pub recovery_time_ms: Option<f32>,
}

/// Comparison of macroscopic temporal alignment between two runs (e.g. Explicit vs LPU).
#[derive(Debug, Default)]
pub struct DynamicsComparison {
    /// Pearson r of the population firing-rate PSTH traces.
    /// This is *population-rate temporal alignment*, not single-unit spike timing.
    pub psth_correlation: f32,
    pub mean_fr_delta_pct: f32,
    pub peak_freq_delta_hz: f32,
    pub cv_pop_delta_pct: f32,
}

impl PopulationDynamics {
    /// Compute all macroscopic dynamic properties from the execution record.
    ///
    /// # Arguments
    /// * `rec`   — execution record returned by `run_explicit` / `run_mixed`.
    /// * `dt_s`  — simulation timestep **in seconds** (e.g. `0.001` for 1 ms).
    pub fn from_record(rec: &RunRecord, dt_s: f32) -> Self {
        let fr_trace = get_fr_trace(rec, dt_s);
        let n = fr_trace.len();
        if n == 0 {
            return Self::default();
        }

        // 1. Mean FR (Hz)
        let mean_fr_hz = fr_trace.iter().sum::<f32>() / n as f32;

        // 2. Synchrony – Population CV = σ(R) / μ(R)
        //    Higher CV_pop → stronger temporal concentration / burstiness.
        //    Threshold interpretation depends on regime, bin width and network size;
        //    report as a relative, not an absolute, synchrony indicator.
        let var = fr_trace
            .iter()
            .map(|&x| (x - mean_fr_hz).powi(2))
            .sum::<f32>()
            / n as f32;
        let cv_pop = if mean_fr_hz > 1e-6 {
            var.sqrt() / mean_fr_hz
        } else {
            0.0
        };

        // 3. Transient Shape
        let dt_ms = dt_s * 1_000.0; // convert to ms for human-readable outputs
        let (max_idx, &max_fr_hz) = fr_trace
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .unwrap_or((0, &0.0));
        let t_peak_ms = max_idx as f32 * dt_ms;

        let t_10 = fr_trace[..=max_idx]
            .iter()
            .position(|&x| x >= 0.1 * max_fr_hz)
            .unwrap_or(0);
        let t_90 = fr_trace[..=max_idx]
            .iter()
            .position(|&x| x >= 0.9 * max_fr_hz)
            .unwrap_or(max_idx);
        let rise_time_10_90_ms = (t_90 as f32 - t_10 as f32) * dt_ms;

        let tail_len = (n / 5).max(1);
        let steady_state = fr_trace[n - tail_len..].iter().sum::<f32>() / tail_len as f32;
        let recovery_threshold = steady_state + 0.5 * (max_fr_hz - steady_state);
        let mut recovery_time_ms = None;
        if max_fr_hz > steady_state + 1e-3 {
            for (i, &val) in fr_trace[max_idx..].iter().enumerate() {
                if val <= recovery_threshold {
                    recovery_time_ms = Some(i as f32 * dt_ms);
                    break;
                }
            }
        }

        // 4. Oscillation Analysis (Hann-windowed DFT)
        let (peak_freq_hz, peak_power) = compute_dominant_oscillation(&fr_trace, dt_s);

        Self {
            mean_fr_hz,
            cv_pop,
            peak_freq_hz,
            peak_power,
            max_fr_hz,
            t_peak_ms,
            rise_time_10_90_ms,
            recovery_time_ms,
        }
    }
}

/// Compare two execution records and return macroscopic alignment metrics.
///
/// `dt_s` must be in **seconds** (same convention as `PopulationDynamics::from_record`).
pub fn compare_dynamics(rec_a: &RunRecord, rec_b: &RunRecord, dt_s: f32) -> DynamicsComparison {
    let dyn_a = PopulationDynamics::from_record(rec_a, dt_s);
    let dyn_b = PopulationDynamics::from_record(rec_b, dt_s);

    let fr_a = get_fr_trace(rec_a, dt_s);
    let fr_b = get_fr_trace(rec_b, dt_s);

    let psth_correlation = if fr_a.len() > 1 && fr_a.len() == fr_b.len() {
        pearson_correlation(&fr_a, &fr_b)
    } else {
        0.0
    };

    DynamicsComparison {
        psth_correlation,
        mean_fr_delta_pct: if dyn_a.mean_fr_hz > 1e-6 {
            (dyn_b.mean_fr_hz - dyn_a.mean_fr_hz) / dyn_a.mean_fr_hz * 100.0
        } else {
            0.0
        },
        peak_freq_delta_hz: dyn_b.peak_freq_hz - dyn_a.peak_freq_hz,
        cv_pop_delta_pct: if dyn_a.cv_pop > 1e-6 {
            (dyn_b.cv_pop - dyn_a.cv_pop) / dyn_a.cv_pop * 100.0
        } else {
            0.0
        },
    }
}

/// Extract the Population Firing Rate PSTH trace in **Hz**.
///
/// `dt_s` — simulation timestep in seconds (e.g. `0.001`).
pub fn get_fr_trace(rec: &RunRecord, dt_s: f32) -> Vec<f32> {
    if rec.total_units == 0 {
        return vec![0.0; rec.steps.len()];
    }
    // spikes / (units × dt_s) = Hz
    let scale = 1.0 / (rec.total_units as f32 * dt_s);
    rec.steps
        .iter()
        .map(|s| s.total_spikes as f32 * scale)
        .collect()
}

/// Compute the dominant oscillation frequency and peak power using a
/// Hann-windowed O(N²) DFT.
///
/// `dt_s` — simulation timestep in seconds.
/// Returns `(peak_freq_hz, normalized_peak_power)`.
pub fn compute_dominant_oscillation(trace: &[f32], dt_s: f32) -> (f32, f32) {
    let n = trace.len();
    if n < 2 {
        return (0.0, 0.0);
    }

    let mean: f32 = trace.iter().sum::<f32>() / n as f32;
    // Demean + apply Hann window to suppress spectral leakage at short N.
    let windowed: Vec<f32> = trace
        .iter()
        .enumerate()
        .map(|(i, &x)| {
            let w = 0.5 * (1.0 - (2.0 * std::f32::consts::PI * i as f32 / (n - 1) as f32).cos());
            (x - mean) * w
        })
        .collect();

    let max_k = n / 2;
    let mut peak_power = 0.0f32;
    let mut peak_k = 0usize;

    // k=0 → DC bin (≈0 after demeaning), skip.
    for k in 1..=max_k {
        let mut re = 0.0f32;
        let mut im = 0.0f32;
        let phase_scale = -2.0 * std::f32::consts::PI * k as f32 / n as f32;
        for (i, &val) in windowed.iter().enumerate() {
            let (sin, cos) = (phase_scale * i as f32).sin_cos();
            re += val * cos;
            im += val * sin;
        }
        // Normalise power by N² so amplitude is independent of trace length.
        let power = (re * re + im * im) / (n as f32 * n as f32);
        if power > peak_power {
            peak_power = power;
            peak_k = k;
        }
    }

    let fs_hz = 1.0 / dt_s; // sampling frequency
    let peak_freq_hz = peak_k as f32 * fs_hz / n as f32;
    (peak_freq_hz, peak_power)
}

/// Pearson Correlation Coefficient $r \in [-1, 1]$ between two equal-length sequences.
pub fn pearson_correlation(x: &[f32], y: &[f32]) -> f32 {
    let n = x.len();
    debug_assert_eq!(n, y.len(), "pearson_correlation: sequences must be equal length");
    let mean_x = x.iter().sum::<f32>() / n as f32;
    let mean_y = y.iter().sum::<f32>() / n as f32;

    let mut num = 0.0f32;
    let mut sum_sq_x = 0.0f32;
    let mut sum_sq_y = 0.0f32;

    for i in 0..n {
        let dx = x[i] - mean_x;
        let dy = y[i] - mean_y;
        num += dx * dy;
        sum_sq_x += dx * dx;
        sum_sq_y += dy * dy;
    }

    let denom = (sum_sq_x * sum_sq_y).sqrt();
    if denom < 1e-9 {
        return 0.0;
    }
    num / denom
}

/// Compute the full power spectral density (Hann-windowed DFT).
///
/// Returns `Vec<(frequency_hz, power)>` from bin 1 (DC+1) up to Nyquist.
/// Suitable for CSV export and the Paper 2 PSD comparison figure.
///
/// `dt_s` — simulation timestep in **seconds** (e.g. `0.001` for 1 ms).
pub fn compute_psd_spectrum(trace: &[f32], dt_s: f32) -> Vec<(f32, f32)> {
    let n = trace.len();
    if n < 2 {
        return vec![];
    }

    let mean: f32 = trace.iter().sum::<f32>() / n as f32;
    // Demean + Hann window — identical processing to `compute_dominant_oscillation`.
    let windowed: Vec<f32> = trace
        .iter()
        .enumerate()
        .map(|(i, &x)| {
            let w =
                0.5 * (1.0 - (2.0 * std::f32::consts::PI * i as f32 / (n - 1) as f32).cos());
            (x - mean) * w
        })
        .collect();

    let fs_hz = 1.0 / dt_s;
    let max_k = n / 2;

    // k=0 is DC (≈0 after demeaning); start at k=1.
    (1..=max_k)
        .map(|k| {
            let mut re = 0.0f32;
            let mut im = 0.0f32;
            let phase_scale = -2.0 * std::f32::consts::PI * k as f32 / n as f32;
            for (i, &val) in windowed.iter().enumerate() {
                let (sin, cos) = (phase_scale * i as f32).sin_cos();
                re += val * cos;
                im += val * sin;
            }
            let power = (re * re + im * im) / (n as f32 * n as f32);
            let freq_hz = k as f32 * fs_hz / n as f32;
            (freq_hz, power)
        })
        .collect()
}

/// Write per-step population FR traces from multiple runs to a CSV for state-space analysis.
///
/// Columns: `step,t_ms,<label1>_fr_hz,<label2>_fr_hz,...`
///
/// `dt_s` — simulation timestep in seconds (e.g. `0.0001` for 0.1 ms).
/// All `RunRecord`s must have the same number of steps.
pub fn write_fr_traces_csv<P: AsRef<std::path::Path>>(
    path: P,
    traces: &[(&str, &RunRecord)],
    dt_s: f32,
) -> std::io::Result<()> {
    use std::io::Write as IoWrite;
    let mut file = std::fs::File::create(path)?;

    // Header
    write!(file, "step,t_ms")?;
    for (label, _) in traces {
        write!(file, ",{label}_fr_hz")?;
    }
    writeln!(file)?;

    let n_steps = traces.first().map(|(_, r)| r.steps.len()).unwrap_or(0);
    let dt_ms = dt_s * 1000.0;

    for i in 0..n_steps {
        write!(file, "{},{:.4}", i, i as f32 * dt_ms)?;
        for (_, rec) in traces {
            let fr = if i < rec.steps.len() && rec.total_units > 0 {
                rec.steps[i].total_spikes as f32 / (rec.total_units as f32 * dt_s)
            } else {
                0.0
            };
            write!(file, ",{fr:.6}")?;
        }
        writeln!(file)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Pearson correlation ────────────────────────────────────────────────────

    #[test]
    fn test_pearson_perfect_positive() {
        let a = vec![1.0_f32, 2.0, 3.0, 4.0, 5.0];
        let b = vec![2.0_f32, 4.0, 6.0, 8.0, 10.0];
        assert!((pearson_correlation(&a, &b) - 1.0).abs() < 1e-5);
    }

    #[test]
    fn test_pearson_perfect_negative() {
        let a = vec![1.0_f32, 2.0, 3.0, 4.0, 5.0];
        let c = vec![5.0_f32, 4.0, 3.0, 2.0, 1.0];
        assert!((pearson_correlation(&a, &c) + 1.0).abs() < 1e-5);
    }

    #[test]
    fn test_pearson_near_zero_uncorrelated() {
        // Orthogonal (zero-mean, 90° phase difference) sequences are uncorrelated.
        // sin and cos over a full period → Pearson r ≈ 0.
        use std::f32::consts::PI;
        let n = 1000;
        let x: Vec<f32> = (0..n)
            .map(|i| (2.0 * PI * i as f32 / n as f32).sin())
            .collect();
        let y: Vec<f32> = (0..n)
            .map(|i| (2.0 * PI * i as f32 / n as f32).cos())
            .collect();
        let r = pearson_correlation(&x, &y);
        assert!(r.abs() < 0.01, "expected r ≈ 0, got {r}");
    }

    // ── DFT / oscillation ──────────────────────────────────────────────────────

    #[test]
    fn test_oscillation_sine_wave() {
        // 40 Hz sine wave, 1000 samples at dt_s = 0.001 (Fs = 1000 Hz).
        let dt_s: f32 = 0.001;
        let fs: f32 = 1.0 / dt_s;
        let f_target: f32 = 40.0;
        let n = 1000_usize;

        let trace: Vec<f32> = (0..n)
            .map(|i| {
                let t = i as f32 / fs;
                10.0 + 5.0 * (2.0 * std::f32::consts::PI * f_target * t).sin()
            })
            .collect();

        let (peak_f, peak_p) = compute_dominant_oscillation(&trace, dt_s);
        // Bin width = Fs/N = 1 Hz at N=1000; allow ±1 bin tolerance.
        assert!(
            (peak_f - f_target).abs() <= 1.0,
            "Expected ~40 Hz, got {peak_f}"
        );
        assert!(peak_p > 0.01, "Expected significant power, got {peak_p}");
    }

    #[test]
    fn test_constant_signal_has_zero_peak_power_after_demean() {
        let trace = vec![5.0_f32; 200];
        let (_, peak_p) = compute_dominant_oscillation(&trace, 0.001);
        assert!(
            peak_p < 1e-8,
            "Constant sequence should have ~0 peak power after demeaning, got {peak_p}"
        );
    }
}
