//! Standardized input protocols for Phase 2 experiments.
//!
//! Defines the external drive applied to the explicit baseline **and** the
//! LPU-replaced model identically, ensuring fair comparison.
//!
//! # Operating Regimes
//! Three regimes are defined, matching the Paper 2 experimental design:
//!
//! 1. **Quiescent**: very weak tonic drive, network remains near-resting;
//!    tests dormant-state fidelity.
//! 2. **Driven**: moderate tonic drive, network sustains ~5–15 Hz activity;
//!    the primary comparison regime for firing-rate and PSD metrics.
//! 3. **Sustained**: strong drive that pushes the network into high-activity;
//!    tests upper-bound LPU fidelity and resource savings at high load.
//!
//! # Drive Types
//! - **Tonic**: constant stimulus injected every step.
//! - **Pulsed**: stimulus injected in bursts (on_slots on, off_slots off).
//! - **Stochastic**: Poisson-like drive with a given mean rate. Uses the same
//!   LCG RNG as `EIMicrocircuitSpec` for reproducibility.

use crate::core::chunk::{ChunkId, DelayedEvent};
use crate::core::scheduler::Scheduler;

/// The three canonical operating regimes used in Phase 2 experiments.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OperatingRegime {
    /// Very weak drive; network remains mostly dormant.
    Quiescent,
    /// Moderate tonic drive; sustained ~5–15 Hz activity. Primary comparison regime.
    Driven,
    /// Strong drive; network saturates. Upper-bound stress test.
    Sustained,
}

/// Drive type for external input protocol.
#[derive(Debug, Clone)]
pub enum DriveType {
    /// Constant stimulus injected every slot.
    Tonic { strength: f32 },
    /// Stimulus injected in on/off bursts.
    Pulsed {
        strength: f32,
        on_slots: u64,
        off_slots: u64,
    },
    /// Poisson-like stochastic drive at mean rate `rate_per_slot` ∈ [0,1].
    Stochastic {
        strength: f32,
        rate_per_slot: f32,
        seed: u64,
    },
}

/// Standardized input protocol for a Phase 2 experiment.
///
/// Applied identically to Mode A (explicit) and Mode B (LPU) runs to
/// satisfy the controlled comparison requirement (Task 3).
#[derive(Debug, Clone)]
pub struct InputProtocol {
    /// Target chunks to receive the external drive.
    pub target_chunks: Vec<ChunkId>,
    /// Type of external drive.
    pub drive: DriveType,
    /// Delay in slots before drive reaches target (typically 0 = immediate).
    pub delay_slots: u64,
}

impl InputProtocol {
    /// Create a tonic protocol for a given regime.
    ///
    /// Strength values chosen to produce the expected regime:
    /// - Quiescent:  0.5 → subthreshold; sparse spontaneous spikes
    /// - Driven:     2.0 → ~10 Hz sustained activity
    /// - Sustained: 10.0 → high-activity saturation
    pub fn for_regime(regime: OperatingRegime, target_chunks: Vec<ChunkId>) -> Self {
        let strength = match regime {
            OperatingRegime::Quiescent => 0.5,
            OperatingRegime::Driven => 2.0,
            OperatingRegime::Sustained => 10.0,
        };
        Self {
            target_chunks,
            drive: DriveType::Tonic { strength },
            delay_slots: 0,
        }
    }

    /// Create a pulsed protocol (on/off burst).
    pub fn pulsed(
        target_chunks: Vec<ChunkId>,
        strength: f32,
        on_slots: u64,
        off_slots: u64,
    ) -> Self {
        Self {
            target_chunks,
            drive: DriveType::Pulsed {
                strength,
                on_slots,
                off_slots,
            },
            delay_slots: 0,
        }
    }

    /// Inject the protocol's drive for the current slot into the scheduler.
    pub fn inject(&self, scheduler: &mut Scheduler) {
        let slot = scheduler.current_slot;

        let strength = match &self.drive {
            DriveType::Tonic { strength } => *strength,
            DriveType::Pulsed {
                strength,
                on_slots,
                off_slots,
            } => {
                let period = on_slots + off_slots;
                if period == 0 {
                    return;
                }
                if slot % period < *on_slots {
                    *strength
                } else {
                    0.0
                }
            }
            DriveType::Stochastic {
                strength,
                rate_per_slot,
                seed,
            } => {
                // Seeded LCG so the same slot always produces the same decision.
                let state = (slot ^ seed)
                    .wrapping_mul(6_364_136_223_846_793_005)
                    .wrapping_add(1_442_695_040_888_963_407);
                let u = ((state >> 40) as f32) / ((1u64 << 24) as f32);
                if u < *rate_per_slot { *strength } else { 0.0 }
            }
        };

        if strength == 0.0 {
            return;
        }

        for &target in &self.target_chunks {
            scheduler.inject_event(DelayedEvent {
                target_chunk: target,
                target_slot: slot + self.delay_slots,
                signal_strength: strength,
            });
        }
    }
}
