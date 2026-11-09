//! Example Use Case 2 (Primary): Panic-Like Runaway Activation Motif.
//!
//! Models a clinically inspired local dynamics motif in which a balanced
//! E/I microcircuit undergoes a mid-simulation inhibition perturbation,
//! leading to a runaway excitatory state followed by (optional) recovery.
//!
//! # Scientific Purpose (Paper 2 Fig 8)
//! This example answers the question:
//! > Can the Phase 2 minimal runtime represent inhibition-sensitive state
//! > transitions — specifically, the onset of runaway activation, its peak,
//! > and delayed recovery — in a minimally connected local circuit?
//!
//! # Interpretation Note
//! This is a **clinically inspired local dynamics motif**, not a full clinical
//! model of panic disorder. It uses inhibitory weight reduction to trigger
//! runaway activation, analogous to a simplified local disinhibition event.
//! The goal is to demonstrate that the system can represent:
//! 1. Stable pre-perturbation baseline (balanced E/I).
//! 2. Abrupt onset of runaway activation after disinhibition.
//! 3. Delayed partial recovery when inhibition is restored.
//!
//! # Simulation Phases
//! ```text
//! ├── Phase 1: Baseline (slots 0..baseline_steps)
//! │   └── Balanced E/I, tonic drive → stable ~oscillatory firing
//! ├── Phase 2: Perturbation (slots baseline_steps..perturb_end)
//! │   └── Inhibitory weight dropped to panic_w_ie → runaway onset
//! └── Phase 3: Recovery (slots perturb_end..total_steps)
//!     └── Inhibitory weight restored → measures recovery
//! ```

use crate::connectivity::{event_router::EventRouter, microcircuit::EIMicrocircuitSpec};
use crate::core::chunk::{Chunk, ChunkId, ChunkStatus, GridCoord};
use crate::core::scheduler::Scheduler;
use crate::experiment::input_protocol::{DriveType, InputProtocol};

/// One row in the panic motif output trajectory.
#[derive(Debug, Clone)]
pub struct PanicStepObs {
    pub slot: u64,
    /// Simulation phase label for this step.
    pub phase: PanicPhase,
    /// Excitatory spikes this step.
    pub exc_spikes: u32,
    /// Inhibitory spikes this step.
    pub inh_spikes: u32,
    /// Number of currently active chunks.
    pub active_chunks: u32,
}

impl PanicStepObs {
    pub fn exc_rate(&self, exc_units: usize) -> f32 {
        self.exc_spikes as f32 / exc_units.max(1) as f32
    }
}

/// Phase label for each simulation step.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PanicPhase {
    Baseline,
    Perturbation,
    Recovery,
}

impl PanicPhase {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Baseline => "Baseline",
            Self::Perturbation => "Perturbation",
            Self::Recovery => "Recovery",
        }
    }
}

/// Full result of one panic motif simulation.
pub struct PanicResult {
    pub trajectory: Vec<PanicStepObs>,
    pub exc_units: usize,
    pub inh_units: usize,
    pub config: PanicMotifConfig,
}

impl PanicResult {
    /// Mean excitatory firing rate in each phase.
    pub fn mean_exc_rate_by_phase(&self, phase: PanicPhase) -> f32 {
        let steps: Vec<&PanicStepObs> = self
            .trajectory
            .iter()
            .filter(|s| s.phase == phase)
            .collect();
        if steps.is_empty() || self.exc_units == 0 {
            return 0.0;
        }
        let total: u32 = steps.iter().map(|s| s.exc_spikes).sum();
        total as f32 / (steps.len() as f32 * self.exc_units as f32)
    }

    /// Peak excitatory rate during perturbation phase.
    pub fn peak_exc_rate_perturbation(&self) -> f32 {
        self.trajectory
            .iter()
            .filter(|s| s.phase == PanicPhase::Perturbation)
            .map(|s| s.exc_rate(self.exc_units))
            .fold(0.0_f32, f32::max)
    }

    /// Onset slot: first slot in Perturbation phase where e_rate > 2× baseline mean.
    pub fn runaway_onset_slot(&self) -> Option<u64> {
        let baseline_mean = self.mean_exc_rate_by_phase(PanicPhase::Baseline);
        let threshold = baseline_mean * 2.0;
        self.trajectory
            .iter()
            .find(|s| s.phase == PanicPhase::Perturbation && s.exc_rate(self.exc_units) > threshold)
            .map(|s| s.slot)
    }

    /// Recovery check: does the mean exc rate in Recovery phase fall below
    /// 150% of baseline within the recovery window?
    pub fn partial_recovery_achieved(&self) -> bool {
        let baseline_mean = self.mean_exc_rate_by_phase(PanicPhase::Baseline);
        let recovery_mean = self.mean_exc_rate_by_phase(PanicPhase::Recovery);
        recovery_mean < baseline_mean * 1.5
    }

    /// Export trajectory as CSV: `phase,slot,exc_rate,inh_spikes,active_chunks`
    pub fn to_csv(&self) -> String {
        let mut lines = vec!["phase,slot,exc_rate,inh_spikes,active_chunks".to_string()];
        for s in &self.trajectory {
            lines.push(format!(
                "{},{},{:.6},{},{}",
                s.phase.label(),
                s.slot,
                s.exc_rate(self.exc_units),
                s.inh_spikes,
                s.active_chunks,
            ));
        }
        lines.join("\n")
    }

    /// Print a phase-level summary table.
    pub fn print_summary(&self) {
        println!("Panic Motif Simulation\n{}", "─".repeat(60));
        println!(
            "{:<14} {:>14} {:>14}",
            "Phase", "Mean E Rate", "Peak E Rate"
        );
        println!("{}", "─".repeat(60));
        for phase in [
            PanicPhase::Baseline,
            PanicPhase::Perturbation,
            PanicPhase::Recovery,
        ] {
            let steps_for_phase: Vec<_> = self
                .trajectory
                .iter()
                .filter(|s| s.phase == phase)
                .collect();
            let peak = steps_for_phase
                .iter()
                .map(|s| s.exc_rate(self.exc_units))
                .fold(0.0_f32, f32::max);
            println!(
                "{:<14} {:>14.4} {:>14.4}",
                phase.label(),
                self.mean_exc_rate_by_phase(phase),
                peak,
            );
        }
        println!("{}", "─".repeat(60));
        println!("Runaway onset:       slot {:?}", self.runaway_onset_slot());
        println!(
            "Partial recovery:    {}",
            if self.partial_recovery_achieved() {
                "YES"
            } else {
                "NO / INCOMPLETE"
            }
        );
    }
}

/// Configuration for the panic motif simulation.
#[derive(Debug, Clone)]
pub struct PanicMotifConfig {
    pub exc_units: usize,
    pub inh_units: usize,
    pub units_per_chunk: usize,
    pub dt: f32,
    /// Number of steps in the stable baseline phase.
    pub baseline_steps: u64,
    /// Number of steps in the perturbation (panic) phase.
    pub perturbation_steps: u64,
    /// Number of steps in the recovery phase.
    pub recovery_steps: u64,
    /// Baseline inhibitory weight (balanced/suppressed E/I).
    pub baseline_w_ie: f32,
    /// Weakened inhibitory weight during perturbation (triggers runaway).
    pub panic_w_ie: f32,
    /// External tonic drive strength to excitatory population.
    pub drive_strength: f32,
    /// E→I synaptic weight.
    ///
    /// Must be strong enough that inh chunks spike when driven by exc:
    /// `exc_rate × w_ei × n_ei_edges × 10 > V_thresh (30)`.
    /// Default 20.0 matches the EI stability calibration.
    pub w_ei: f32,
    /// I→E connection probability.
    ///
    /// Use 1.0 (default) to guarantee I→E edges and avoid the 13% chance
    /// of zero edges that occurs at p=0.4 with only 4 chunk pairs.
    pub p_ie: f32,
    /// E→I connection probability.
    pub p_ei: f32,
}

impl Default for PanicMotifConfig {
    fn default() -> Self {
        Self {
            exc_units: 400,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            baseline_steps: 100,
            perturbation_steps: 100,
            recovery_steps: 100,
            // Calibrated parameters (matches EIStabilityConfig calibration):
            //   drive=8.0  → g_exc_ss=80, exc fires at ~10-step period
            //   w_ei=20, p_ei=0.8 → E→I signal ≥ 60/step → inh chunks spike reliably
            //   baseline_w_ie=300, p_ie=1.0 → g_inh_ss=1200 ≫ g_exc_ss-30 → Quiescent
            //   panic_w_ie=0.001 → g_inh_ss≈0 → Runaway (3× baseline rate)
            // Recovery: restoring baseline_w_ie=300 quickly suppresses runaway activity.
            drive_strength: 8.0,
            baseline_w_ie: 300.0,
            panic_w_ie: 0.001,
            w_ei: 20.0,
            p_ie: 1.0, // deterministic: guarantees all (inh,exc) pairs get an edge
            p_ei: 0.8,
        }
    }
}

/// Build a fresh scheduler for the panic motif simulation.
fn build_scheduler(
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
    units_per_chunk: usize,
    dt: f32,
) -> Scheduler {
    let mut scheduler = Scheduler::new(dt);
    for &id in exc_ids.iter().chain(inh_ids.iter()) {
        let mut chunk = Chunk::new(
            id,
            GridCoord {
                x: id.0 as i32,
                y: 0,
                z: 0,
            },
            units_per_chunk,
            10.0,
        );
        chunk.status = ChunkStatus::Dormant;
        scheduler.add_chunk(chunk);
    }
    scheduler
}

/// Run the full panic motif simulation across three phases.
///
/// Connectivity is rebuilt at each phase boundary to change the inhibitory
/// weight, reflecting the instantaneous disinhibition event. This is the
/// simplest representation of an abrupt local-inhibition change.
pub fn run_panic_motif(config: &PanicMotifConfig) -> PanicResult {
    let n_exc = config.exc_units.div_ceil(config.units_per_chunk);
    let n_inh = config.inh_units.div_ceil(config.units_per_chunk);
    let total_chunks = n_exc + n_inh;

    let exc_ids: Vec<ChunkId> = (0..n_exc as u32).map(ChunkId).collect();
    let inh_ids: Vec<ChunkId> = (n_exc as u32..total_chunks as u32).map(ChunkId).collect();

    let protocol = InputProtocol {
        target_chunks: exc_ids.clone(),
        drive: DriveType::Tonic {
            strength: config.drive_strength,
        },
        delay_slots: 0,
    };

    let mut trajectory = Vec::new();

    // ── Helper: run N steps with given router, appending to trajectory ────────
    let run_phase = |scheduler: &mut Scheduler,
                     router: &EventRouter,
                     n_steps: u64,
                     phase: PanicPhase,
                     trajectory: &mut Vec<PanicStepObs>| {
        for _ in 0..n_steps {
            protocol.inject(scheduler);
            let metrics = scheduler.step();
            router.route_spikes(scheduler, 1.0 / config.units_per_chunk as f32);

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

            trajectory.push(PanicStepObs {
                slot: scheduler.current_slot,
                phase,
                exc_spikes,
                inh_spikes,
                active_chunks: metrics.active_chunk_count,
            });
        }
    };

    // ── Phase 1: Baseline ─────────────────────────────────────────────────────
    let baseline_spec = EIMicrocircuitSpec {
        w_ie: config.baseline_w_ie,
        w_ei: config.w_ei,
        p_ie: config.p_ie,
        p_ei: config.p_ei,
        ..EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone())
    };
    let baseline_mc = baseline_spec.build();
    let baseline_router = EventRouter::from_projections(
        &[
            &baseline_mc.ee,
            &baseline_mc.ei,
            &baseline_mc.ie,
            &baseline_mc.ii,
        ],
        total_chunks,
    );
    let mut scheduler = build_scheduler(&exc_ids, &inh_ids, config.units_per_chunk, config.dt);
    run_phase(
        &mut scheduler,
        &baseline_router,
        config.baseline_steps,
        PanicPhase::Baseline,
        &mut trajectory,
    );

    // ── Phase 2: Perturbation (panic: weakened inhibition) ────────────────────
    // Rebuild router with reduced w_ie; scheduler state carries over (voltages, conductances).
    let panic_spec = EIMicrocircuitSpec {
        w_ie: config.panic_w_ie,
        w_ei: config.w_ei,
        p_ie: config.p_ie,
        p_ei: config.p_ei,
        ..EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone())
    };
    let panic_mc = panic_spec.build();
    let panic_router = EventRouter::from_projections(
        &[&panic_mc.ee, &panic_mc.ei, &panic_mc.ie, &panic_mc.ii],
        total_chunks,
    );
    run_phase(
        &mut scheduler,
        &panic_router,
        config.perturbation_steps,
        PanicPhase::Perturbation,
        &mut trajectory,
    );

    // ── Phase 3: Recovery (restore inhibition) ────────────────────────────────
    // Reuse the baseline router (same weights).
    run_phase(
        &mut scheduler,
        &baseline_router,
        config.recovery_steps,
        PanicPhase::Recovery,
        &mut trajectory,
    );

    PanicResult {
        trajectory,
        exc_units: config.exc_units,
        inh_units: config.inh_units,
        config: config.clone(),
    }
}
