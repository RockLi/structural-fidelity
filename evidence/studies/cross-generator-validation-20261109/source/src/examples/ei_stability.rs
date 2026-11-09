//! Example Use Case 1 (Primary): E/I Stability Regimes.
//!
//! Sweeps the inhibitory weight of a balanced E/I microcircuit across three
//! distinct dynamical regimes and records per-step firing-rate trajectories.
//!
//! # Scientific Purpose (Paper 2 Fig 7)
//! This example answers the question:
//! > Does the Phase 2 minimal connected runtime support qualitatively distinct
//! > local dynamical regimes, and can LPU replacement preserve regime identity?
//!
//! # Three regimes tested
//! | Regime | w_ie override | Expected dynamics |
//! |:---|:---:|:---|
//! | **Quiescent** | 50.0 (strong inh) | Inhibitory feedback suppresses excitatory firing to near-zero |
//! | **Oscillatory** |  5.0 (moderate)  | Partial suppression; moderate sustained rate |
//! | **Runaway**     |  0.01 (weak inh) | Basically no inhibitory feedback; max excitatory firing |
//!
//! # Calibration notes
//! The LIF threshold is 30 mV and `g_exc_ss = drive_strength / dt`.
//! For inhibitory feedback to close the loop:
//!   1. E→I must be strong enough that inh chunks fire:
//!      `g_inh_ss_for_inh = exc_rate × w_ei × n_ei_edges × 10 > 30`
//!      → requires `w_ei ≈ 20`, `p_ei ≈ 0.8`, `drive_strength ≈ 8.0`.
//!   2. I→E must suppress excitatory i_syn below threshold:
//!      `g_inh_ss = inh_rate × w_ie × n_ie_edges × 10 > g_exc_ss − 30`
//!      → requires `w_ie_Q ≈ 50`.
//!
//! # Output
//! A `StabilityResult` containing per-step spike-rate trajectories for each
//! regime, plus a CSV-formatted summary for plotting.

use crate::connectivity::{event_router::EventRouter, microcircuit::EIMicrocircuitSpec};
use crate::core::chunk::{Chunk, ChunkId, ChunkStatus, GridCoord};
use crate::core::scheduler::Scheduler;
use crate::experiment::input_protocol::{DriveType, InputProtocol};

/// Dynamical regime label.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Regime {
    Quiescent,
    Oscillatory,
    Runaway,
}

impl Regime {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Quiescent => "Quiescent",
            Self::Oscillatory => "Oscillatory",
            Self::Runaway => "Runaway",
        }
    }

    /// Inhibitory weight override for this regime.
    ///
    /// Values are calibrated (Task 8) so that the inhibitory feedback loop
    /// closes and produces materially different excitatory firing rates:
    ///   - Quiescent (300.0): g_inh_ss = inh_rate × 300 × n_ie × 10 ≫ g_exc_ss − 30
    ///     → strong suppression, exc driven to oscillatory/near-zero
    ///   - Oscillatory (30.0): partial suppression, intermediate mean rate
    ///   - Runaway   (0.001): negligible I→E feedback, free excitatory firing
    pub fn w_ie(&self) -> f32 {
        match self {
            Self::Quiescent => 300.0,
            Self::Oscillatory => 30.0,
            Self::Runaway => 0.001,
        }
    }
}

/// Per-step observation for one simulation step.
#[derive(Debug, Clone)]
pub struct StepObs {
    pub slot: u64,
    /// Total spikes emitted by the excitatory population this step.
    pub exc_spikes: u32,
    /// Total spikes emitted by the inhibitory population this step.
    pub inh_spikes: u32,
    /// Number of active chunks.
    pub active_chunks: u32,
}

impl StepObs {
    /// Excitatory firing rate (spikes per unit per step).
    pub fn exc_rate(&self, exc_units: usize) -> f32 {
        self.exc_spikes as f32 / exc_units as f32
    }
}

/// Result from one regime run.
#[derive(Debug)]
pub struct RegimeRun {
    pub regime: Regime,
    pub trajectory: Vec<StepObs>,
    pub exc_units: usize,
    pub inh_units: usize,
}

impl RegimeRun {
    /// Mean excitatory firing rate over the run (spikes / unit / step).
    pub fn mean_exc_rate(&self) -> f32 {
        if self.trajectory.is_empty() || self.exc_units == 0 {
            return 0.0;
        }
        let total: u32 = self.trajectory.iter().map(|s| s.exc_spikes).sum();
        total as f32 / (self.trajectory.len() as f32 * self.exc_units as f32)
    }

    /// Peak excitatory firing rate over the run.
    pub fn peak_exc_rate(&self) -> f32 {
        self.trajectory
            .iter()
            .map(|s| s.exc_rate(self.exc_units))
            .fold(0.0_f32, f32::max)
    }

    /// Export trajectory as CSV lines: `slot,exc_rate,inh_spikes,active_chunks`
    pub fn to_csv_lines(&self) -> Vec<String> {
        self.trajectory
            .iter()
            .map(|s| {
                format!(
                    "{},{:.6},{},{}",
                    s.slot,
                    s.exc_rate(self.exc_units),
                    s.inh_spikes,
                    s.active_chunks
                )
            })
            .collect()
    }

    pub fn summary(&self) -> String {
        format!(
            "[{}] mean_exc_rate={:.4} peak_exc_rate={:.4} steps={}",
            self.regime.label(),
            self.mean_exc_rate(),
            self.peak_exc_rate(),
            self.trajectory.len(),
        )
    }
}

/// Full result of the E/I stability sweep.
///
/// Fields are `Option` because the caller may configure a subset of regimes
/// via `EIStabilityConfig::regimes`. Unconfigured regimes are `None`.
pub struct StabilityResult {
    pub quiescent: Option<RegimeRun>,
    pub oscillatory: Option<RegimeRun>,
    pub runaway: Option<RegimeRun>,
}

impl StabilityResult {
    /// Print a plain-text regime comparison table.
    pub fn print_table(&self) {
        println!("E/I Stability Regime Sweep");
        println!("{}", "─".repeat(60));
        println!(
            "{:<14} {:>14} {:>14}",
            "Regime", "Mean E Rate", "Peak E Rate"
        );
        println!("{}", "─".repeat(60));
        for run in [&self.quiescent, &self.oscillatory, &self.runaway]
            .iter()
            .filter_map(|r| r.as_ref())
        {
            println!(
                "{:<14} {:>14.4} {:>14.4}",
                run.regime.label(),
                run.mean_exc_rate(),
                run.peak_exc_rate(),
            );
        }
        println!("{}", "─".repeat(60));
    }

    /// Export all configured regime trajectories as a single CSV block.
    /// Format: `regime,slot,exc_rate,inh_spikes,active_chunks`
    pub fn to_csv(&self) -> String {
        let mut lines = vec!["regime,slot,exc_rate,inh_spikes,active_chunks".to_string()];
        for run in [&self.quiescent, &self.oscillatory, &self.runaway]
            .iter()
            .filter_map(|r| r.as_ref())
        {
            for csv_line in run.to_csv_lines() {
                lines.push(format!("{},{}", run.regime.label(), csv_line));
            }
        }
        lines.join("\n")
    }
}

/// Configuration for the E/I stability example run.
pub struct EIStabilityConfig {
    pub exc_units: usize,
    pub inh_units: usize,
    pub units_per_chunk: usize,
    pub dt: f32,
    pub num_steps: u64,
    /// External tonic drive strength applied to excitatory population.
    ///
    /// Set near the spike threshold: `drive_strength / dt ≈ 80` (8.0 with dt=0.1)
    /// so excitatory units fire at ~10% rate, giving inhibitory chunks enough
    /// drive to reach threshold via E→I connections.
    pub drive_strength: f32,
    /// E→I synaptic weight.
    ///
    /// Must be large enough that inh chunks spike when driven by exc:
    /// `exc_rate × w_ei × n_ei_edges × 10 > V_thresh (30).`
    /// Default: 20.0 (with p_ei=0.8 gives ≈8 edges → inh fires at exc_rate ≥ 0.05).
    pub w_ei: f32,
    /// I→E probability of connection (controls n_ie_edges per exc chunk).
    pub p_ie: f32,
    /// E→I probability of connection (controls n_ei_edges per inh chunk).
    pub p_ei: f32,
    /// Regimes to sweep. Defaults to all three.
    pub regimes: Vec<Regime>,
}

impl Default for EIStabilityConfig {
    fn default() -> Self {
        Self {
            exc_units: 400,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            num_steps: 200,
            // Calibrated parameters for visible E/I regime differentiation:
            //   drive=8.0 → g_exc_ss=80 → exc fires at ~10 Hz period
            //   w_ei=20, p_ei=0.8 → E→I signal per step ≥ 60 → inh spikes reliably
            //   w_ie_Q=300, p_ie=1.0 → guaranteed 4 I→E edges; g_inh_ss=1200 ≫ g_exc_ss-30
            //   w_ie_R=0.001 → g_inh_ss≈0 → Runaway fires freely
            // p_ie=1.0 avoids the 13% chance of 0 I→E edges with p=0.4 and only 4 pairs.
            drive_strength: 8.0,
            w_ei: 20.0,
            p_ie: 1.0, // deterministic: all (inh,exc) pairs get one I→E edge
            p_ei: 0.8,
            regimes: vec![Regime::Quiescent, Regime::Oscillatory, Regime::Runaway],
        }
    }
}

/// Run the E/I stability sweep for one regime.
fn run_regime(cfg: &EIStabilityConfig, regime: Regime) -> RegimeRun {
    let n_exc_chunks = cfg.exc_units.div_ceil(cfg.units_per_chunk);
    let n_inh_chunks = cfg.inh_units.div_ceil(cfg.units_per_chunk);

    let exc_ids: Vec<ChunkId> = (0..n_exc_chunks as u32).map(ChunkId).collect();
    let inh_ids: Vec<ChunkId> = (n_exc_chunks as u32..(n_exc_chunks + n_inh_chunks) as u32)
        .map(ChunkId)
        .collect();

    // Build microcircuit with regime-specific inhibitory weight and
    // example-calibrated E→I weights (p_ei, w_ei) to ensure the inhibitory
    // loop closes at the configured drive level.
    let spec = EIMicrocircuitSpec {
        w_ie: regime.w_ie(),
        w_ei: cfg.w_ei,
        p_ie: cfg.p_ie,
        p_ei: cfg.p_ei,
        ..EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone())
    };
    let mc = spec.build();
    let projs = vec![&mc.ee, &mc.ei, &mc.ie, &mc.ii];
    let router = EventRouter::from_projections(&projs, n_exc_chunks + n_inh_chunks);

    // Build scheduler.
    let mut scheduler = Scheduler::new(cfg.dt);
    for &id in exc_ids.iter().chain(inh_ids.iter()) {
        let mut chunk = Chunk::new(
            id,
            GridCoord {
                x: id.0 as i32,
                y: 0,
                z: 0,
            },
            cfg.units_per_chunk,
            10.0,
        );
        chunk.status = ChunkStatus::Dormant;
        scheduler.add_chunk(chunk);
    }

    // External tonic drive to excitatory population only.
    let protocol = InputProtocol {
        target_chunks: exc_ids.clone(),
        drive: DriveType::Tonic {
            strength: cfg.drive_strength,
        },
        delay_slots: 0,
    };

    let mut trajectory = Vec::with_capacity(cfg.num_steps as usize);

    for _step in 0..cfg.num_steps {
        protocol.inject(&mut scheduler);
        let metrics = scheduler.step();
        router.route_spikes(&mut scheduler, 1.0 / cfg.units_per_chunk as f32);

        // Count spikes separately for E and I populations.
        let exc_spikes: u32 = exc_ids
            .iter()
            .filter_map(|id| scheduler.chunks.get(id))
            .map(|c| c.state.spike_flags.iter().sum::<f32>() as u32)
            .sum();
        let inh_spikes: u32 = inh_ids
            .iter()
            .filter_map(|id| scheduler.chunks.get(id))
            .map(|c| c.state.spike_flags.iter().sum::<f32>() as u32)
            .sum();

        trajectory.push(StepObs {
            slot: scheduler.current_slot,
            exc_spikes,
            inh_spikes,
            active_chunks: metrics.active_chunk_count,
        });
    }

    RegimeRun {
        regime,
        trajectory,
        exc_units: cfg.exc_units,
        inh_units: cfg.inh_units,
    }
}

/// Run the E/I stability sweep for the regimes listed in `cfg.regimes`.
///
/// Unconfigured regimes are `None` in the returned `StabilityResult`.
pub fn run_stability_sweep(cfg: &EIStabilityConfig) -> StabilityResult {
    let mut quiescent = None;
    let mut oscillatory = None;
    let mut runaway = None;

    for &regime in &cfg.regimes {
        let run = run_regime(cfg, regime);
        match regime {
            Regime::Quiescent => quiescent = Some(run),
            Regime::Oscillatory => oscillatory = Some(run),
            Regime::Runaway => runaway = Some(run),
        }
    }

    StabilityResult {
        quiescent,
        oscillatory,
        runaway,
    }
}
