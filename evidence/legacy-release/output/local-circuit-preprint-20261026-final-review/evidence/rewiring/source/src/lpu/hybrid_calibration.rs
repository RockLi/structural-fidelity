//! Hybrid-mode 2D calibration sweep for Phase 3.
//!
//! Systematically searches the `(gain_fast_exc, gain_fast_inh)` plane for
//! `RicherProxyParams` values that minimise E/I imbalance in the proxy sub-path
//! of a mixed-mode (`run_mixed_with_retention`) simulation.
//!
//! # Motivation
//! Selective explicit retention can cause severe
//! underfiring in E1 (spike_ratio 0.474, FR-delta −52.6%) when the remaining
//! proxy backbone uses uncalibrated default gains.  The explicit path correctly
//! routes inhibitory braking, but the proxy still applies its full inhibitory
//! gain on the replaced edges, double-counting suppression.
//!
//! Reducing `gain_fast_inh` in the proxy sub-path compensates.  This module
//! automates a coarse grid search to identify the (exc, inh) gain region that
//! restores PSTH-r ≥ `4ch-default` while keeping spike_ratio ≤ 1.5.
//!
//! # Usage
//! ```rust,ignore
//! let grid = sweep_2d(
//!     "bench_e1_calibrated",
//!     &base_cfg, &mc, &policy, &exc_ids, &inh_ids, &rec_explicit,
//!     &[1.0, 2.0, 4.0],   // gain_fast_exc candidates
//!     &[0.1, 0.3, 0.6],   // gain_fast_inh candidates
//!     DT_S,
//! );
//! if let Some(best) = grid.best_go() {
//!     println!("Best calibrated params: {}", best.summary());
//! }
//! ```

use crate::connectivity::microcircuit::EIMicrocircuit;
use crate::core::chunk::ChunkId;
use crate::experiment::frontier::FrontierPoint;
use crate::experiment::harness::{HarnessConfig, RunRecord, run_mixed_with_retention};
use crate::experiment::retention::RetentionPolicy;
use crate::lpu::proxy_params::RicherProxyParams;

/// One cell in the 2D calibration grid.
#[derive(Debug, Clone)]
pub struct HybridCalibrationResult {
    pub gain_fast_exc: f32,
    pub gain_fast_inh: f32,
    pub point: FrontierPoint,
}

impl HybridCalibrationResult {
    /// One-line summary for test output.
    pub fn summary(&self) -> String {
        format!(
            "gfe={:.3} gfi={:.3} → psth_r={:.3} fr_delta={:+.1}% \
             spike_ratio={:.3} ret_e={:.1}% ev_share={:.1}% {}",
            self.gain_fast_exc,
            self.gain_fast_inh,
            self.point.psth_correlation,
            self.point.mean_fr_delta_pct,
            self.point.spike_ratio,
            self.point.retained_edges_pct,
            self.point.explicit_event_share_pct,
            if self.point.meets_go_criteria() { "GO" } else { "STOP" },
        )
    }
}

/// Aggregated results of a 2D `(gain_fast_exc, gain_fast_inh)` calibration sweep.
#[derive(Debug)]
pub struct HybridCalibrationGrid {
    pub benchmark: String,
    pub results: Vec<HybridCalibrationResult>,
}

impl HybridCalibrationGrid {
    /// Best result that meets `FrontierPoint::meets_go_criteria()`, ranked by PSTH-r.
    pub fn best_go(&self) -> Option<&HybridCalibrationResult> {
        self.results
            .iter()
            .filter(|r| r.point.meets_go_criteria())
            .max_by(|a, b| {
                a.point
                    .psth_correlation
                    .partial_cmp(&b.point.psth_correlation)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
    }

    /// Best result by PSTH-r regardless of Go criteria.
    pub fn best_fidelity(&self) -> Option<&HybridCalibrationResult> {
        self.results.iter().max_by(|a, b| {
            a.point
                .psth_correlation
                .partial_cmp(&b.point.psth_correlation)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
    }

    /// Best result by lowest `spike_ratio` (cheapest) that still has finite PSTH-r.
    pub fn cheapest(&self) -> Option<&HybridCalibrationResult> {
        self.results
            .iter()
            .filter(|r| r.point.spike_ratio.is_finite())
            .min_by(|a, b| {
                a.point
                    .spike_ratio
                    .partial_cmp(&b.point.spike_ratio)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
    }

    /// Build `RicherProxyParams` with `gain_fast_exc` and `gain_fast_inh` overridden
    /// from the given calibration result (all other fields come from `base`).
    pub fn calibrated_params(base: &RicherProxyParams, r: &HybridCalibrationResult) -> RicherProxyParams {
        RicherProxyParams {
            gain_fast_exc: r.gain_fast_exc,
            gain_fast_inh: r.gain_fast_inh,
            ..base.clone()
        }
    }

    /// Multi-line summary table for test output.
    pub fn summary_table(&self) -> String {
        let mut out = format!("[HybridCalibrationGrid: {}]\n", self.benchmark);
        for r in &self.results {
            out.push_str(&format!("  {}\n", r.summary()));
        }
        if let Some(best) = self.best_go() {
            out.push_str(&format!("  → Best GO: {}\n", best.summary()));
        } else if let Some(best) = self.best_fidelity() {
            out.push_str(&format!("  → Best fidelity (no GO): {}\n", best.summary()));
        }
        out
    }
}

/// Run a 2D calibration sweep over `(gain_fast_exc, gain_fast_inh)` pairs.
///
/// For each pair, calls `run_mixed_with_retention` with the given policy and
/// records a `FrontierPoint` vs. `rec_explicit`.
///
/// # Arguments
/// - `base_cfg`: template config; `router` and `lpu_index` are **ignored** (rebuilt
///   internally by `run_mixed_with_retention`).  `richer_params` is used as a base
///   for all other proxy params (tau values, slow-channel gains, etc.).
/// - `full_circuit`: the complete circuit to partition.
/// - `policy`: the `RetentionPolicy` applied at each sweep point.
/// - `gain_fast_exc_values` / `gain_fast_inh_values`: candidate gain values.
/// - `dt_s`: simulation timestep in seconds (for `FrontierPoint` calculation).
pub fn sweep_2d(
    benchmark: impl Into<String>,
    base_cfg: &HarnessConfig,
    full_circuit: &EIMicrocircuit,
    policy: &RetentionPolicy,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
    rec_explicit: &RunRecord,
    gain_fast_exc_values: &[f32],
    gain_fast_inh_values: &[f32],
    dt_s: f32,
) -> HybridCalibrationGrid {
    let mut results = Vec::new();

    for &gfe in gain_fast_exc_values {
        for &gfi in gain_fast_inh_values {
            let richer = RicherProxyParams {
                gain_fast_exc: gfe,
                gain_fast_inh: gfi,
                ..base_cfg.richer_params.clone()
            };

            // Construct a fresh sweep config with overridden gains.
            // router/lpu_index are set to None; run_mixed_with_retention builds its own.
            let sweep_cfg = HarnessConfig {
                exc_units: base_cfg.exc_units,
                inh_units: base_cfg.inh_units,
                units_per_chunk: base_cfg.units_per_chunk,
                dt: base_cfg.dt,
                num_steps: base_cfg.num_steps,
                input_protocol: base_cfg.input_protocol.clone(),
                router: None,
                lpu_params: base_cfg.lpu_params.clone(),
                replaced_circuit: None,
                lpu_index: None,
                proxy_mode: base_cfg.proxy_mode,
                richer_params: richer,
            };

            let ret_result =
                run_mixed_with_retention(&sweep_cfg, full_circuit, policy, exc_ids, inh_ids);
            let pt = FrontierPoint::from_retention_result(
                format!("gfe={:.2}_gfi={:.2}", gfe, gfi),
                rec_explicit,
                &ret_result,
                dt_s,
            );

            results.push(HybridCalibrationResult {
                gain_fast_exc: gfe,
                gain_fast_inh: gfi,
                point: pt,
            });
        }
    }

    HybridCalibrationGrid {
        benchmark: benchmark.into(),
        results,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::connectivity::event_router::EventRouter;
    use crate::connectivity::microcircuit::EIMicrocircuitSpec;
    use crate::experiment::harness::{HarnessConfig, run_explicit};
    use crate::experiment::input_protocol::{InputProtocol, OperatingRegime};
    use crate::experiment::retention::{MotifClass, RetentionPolicy};
    use crate::lpu::aggregator::AggregatorParams;
    use crate::lpu::proxy::ProxyMode;

    fn make_small_explicit_baseline(
        exc_ids: &[ChunkId],
        inh_ids: &[ChunkId],
        mc: &EIMicrocircuit,
    ) -> RunRecord {
        let n_chunks = exc_ids.len() + inh_ids.len();
        let projs = mc.all_proj_refs();
        let router = EventRouter::from_projections(&projs, n_chunks);
        let cfg = HarnessConfig {
            exc_units: exc_ids.len() * 100,
            inh_units: inh_ids.len() * 100,
            units_per_chunk: 100,
            dt: 0.1,
            num_steps: 100,
            input_protocol: InputProtocol::for_regime(
                OperatingRegime::Sustained,
                exc_ids.to_vec(),
            ),
            router: Some(router),
            lpu_params: AggregatorParams::default(),
            replaced_circuit: None,
            lpu_index: None,
            proxy_mode: ProxyMode::FourChannel,
            richer_params: RicherProxyParams::default(),
        };
        run_explicit(&cfg)
    }

    #[test]
    fn test_sweep_2d_returns_correct_grid_size() {
        let exc_ids: Vec<ChunkId> = (0..4).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..5).map(ChunkId).collect();
        let mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();
        let rec_explicit = make_small_explicit_baseline(&exc_ids, &inh_ids, &mc);

        let mc2 = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();
        let policy = RetentionPolicy::new(vec![MotifClass::StrongInhibitoryLoop], 1.0);
        let base_cfg = HarnessConfig {
            exc_units: 400,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            num_steps: 50,
            input_protocol: InputProtocol::for_regime(
                OperatingRegime::Sustained,
                exc_ids.clone(),
            ),
            router: None,
            lpu_params: AggregatorParams::default(),
            replaced_circuit: None,
            lpu_index: None,
            proxy_mode: ProxyMode::FourChannel,
            richer_params: RicherProxyParams::default(),
        };

        let grid = sweep_2d(
            "test_2d",
            &base_cfg,
            &mc2,
            &policy,
            &exc_ids,
            &inh_ids,
            &rec_explicit,
            &[1.0, 3.0],
            &[0.2, 0.5],
            0.0001,
        );

        assert_eq!(
            grid.results.len(),
            4,
            "2×2 sweep must produce 4 results"
        );
        for r in &grid.results {
            assert!(
                r.point.psth_correlation.is_finite(),
                "every sweep point must have finite PSTH-r"
            );
        }
    }

    #[test]
    fn test_calibrated_params_overrides_gains() {
        let base = RicherProxyParams::default();
        let result = HybridCalibrationResult {
            gain_fast_exc: 3.5,
            gain_fast_inh: 0.2,
            point: FrontierPoint {
                label: "test".into(),
                proxy_events: 0,
                explicit_events: 0,
                event_ratio: 1.0,
                spike_ratio: 1.0,
                explicit_spikes: 0,
                proxy_spikes: 0,
                psth_correlation: 0.8,
                mean_fr_delta_pct: 5.0,
                cv_pop_delta_pct: 3.0,
                peak_freq_delta_hz: 0.0,
                explicit_mean_fr_hz: 10.0,
                proxy_mean_fr_hz: 10.5,
                retained_edges_pct: 12.0,
                explicit_event_share_pct: 8.0,
            },
        };
        let calibrated = HybridCalibrationGrid::calibrated_params(&base, &result);
        assert!(
            (calibrated.gain_fast_exc - 3.5).abs() < 1e-6,
            "gain_fast_exc must be overridden"
        );
        assert!(
            (calibrated.gain_fast_inh - 0.2).abs() < 1e-6,
            "gain_fast_inh must be overridden"
        );
        assert!(
            (calibrated.gain_slow_exc - base.gain_slow_exc).abs() < 1e-6,
            "other fields must be preserved from base"
        );
    }
}
