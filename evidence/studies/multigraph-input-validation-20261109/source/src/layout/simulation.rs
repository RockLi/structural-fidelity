//! Stage 1.4.3: Runtime Control Surface — `Simulation`
//!
//! `Simulation` is the single user-facing entry point for running the
//! neural simulation. It wraps the Scheduler, exposes `step()` / `run()`,
//! and provides a structured `SimulationMetrics` snapshot.
//!
//! # Usage
//! ```rust
//! use next_brain::layout::{NetworkBuilder, RegionSpec, PopulationSpec, RegionId, Simulation};
//!
//! let layout = NetworkBuilder::new()
//!     .add_region(RegionSpec::new("V1", "Primary Visual Cortex")
//!         .add_population(PopulationSpec::new("V1_exc", RegionId::new("V1"), 100_000)))
//!     .compile()
//!     .unwrap();
//!
//! let mut sim = Simulation::from_layout(layout, 0.001);
//! sim.run(1_000);
//! println!("{:?}", sim.get_metrics());
//! ```

use crate::core::scheduler::{Scheduler, SchedulerStepMetrics};
use crate::layout::builder::CompiledLayout;

/// Aggregated per-step metrics snapshot from the simulation.
#[derive(Debug, Clone, Default)]
pub struct SimulationMetrics {
    /// Current simulation step (slot).
    pub current_slot: u64,
    /// Total steps executed so far.
    pub steps_completed: u64,

    // ── Activity ──────────────────────────────────────────────────────────────
    /// Number of chunks that were active (stepped) in the last step.
    pub active_chunks: u32,
    /// Number of chunks that were skipped (dormant) in the last step.
    pub dormant_skipped: u32,
    /// Total spikes produced across all active chunks in the last step.
    pub total_spikes: u32,

    // ── Event flow ────────────────────────────────────────────────────────────
    /// Delayed events processed in the last step.
    pub event_count: u32,
    /// Chunks that woke from Dormant/PendingWakeUp → Active in the last step.
    pub wakeup_count: u32,

    // ── Timing breakdown (µs) ─────────────────────────────────────────────────
    /// Wall-clock time for the wake-up scan phase (µs).
    pub phase_wakeup_us: u64,
    /// Wall-clock time for the dormant-skip phase (µs).
    pub phase_dormant_us: u64,
    /// Wall-clock time for the active-chunk update phase (µs).
    pub phase_chunk_update_us: u64,
    /// Wall-clock time for the active-set rebuild phase (µs).
    pub phase_set_rebuild_us: u64,
    /// Total wall-clock time for the step (µs).
    pub step_duration_us: u64,
}

impl SimulationMetrics {
    pub fn summary(&self) -> String {
        format!(
            "[slot={:>8}] active={:>6}  dormant_skip={:>8}  wakeup={:>4}  \
             events={:>6}  spikes={:>8}  step={}µs",
            self.current_slot,
            self.active_chunks,
            self.dormant_skipped,
            self.wakeup_count,
            self.event_count,
            self.total_spikes,
            self.step_duration_us,
        )
    }
}

/// The primary runtime controller for a compiled network.
///
/// Owns the `Scheduler` (which owns all the `Chunk`s) and provides safe,
/// structured access to the simulation loop.
pub struct Simulation {
    scheduler: Scheduler,
    /// Timestep delta (ms).
    pub dt: f32,
    /// Latest step metrics (updated after each `step()` call).
    last_metrics: SimulationMetrics,
    /// Total steps executed.
    steps_completed: u64,
}

impl Simulation {
    /// Build a `Simulation` from a `CompiledLayout`.
    ///
    /// Consumes the layout and loads all chunks into the scheduler.
    pub fn from_layout(layout: CompiledLayout, dt: f32) -> Self {
        let mut scheduler = Scheduler::new(dt);
        for chunk in layout.chunks {
            scheduler.add_chunk(chunk);
        }
        Self {
            scheduler,
            dt,
            last_metrics: SimulationMetrics::default(),
            steps_completed: 0,
        }
    }

    /// Advance the simulation by a single timestep.
    ///
    /// Updates internal metrics. Returns a reference to the updated metrics.
    pub fn step(&mut self) -> &SimulationMetrics {
        let m: SchedulerStepMetrics = self.scheduler.step();
        self.steps_completed += 1;

        self.last_metrics = SimulationMetrics {
            current_slot: self.scheduler.current_slot,
            steps_completed: self.steps_completed,
            active_chunks: m.active_chunk_count,
            dormant_skipped: m.dormant_skip_count,
            total_spikes: m.total_spikes,
            event_count: m.event_count,
            wakeup_count: m.wakeup_count,
            phase_wakeup_us: m.phase_wakeup_us,
            phase_dormant_us: m.phase_dormant_us,
            phase_chunk_update_us: m.phase_chunk_update_us,
            phase_set_rebuild_us: m.phase_set_rebuild_us,
            step_duration_us: m.step_duration_us,
        };

        &self.last_metrics
    }

    /// Run the simulation for `num_steps` steps.
    ///
    /// Returns the final `SimulationMetrics` snapshot.
    pub fn run(&mut self, num_steps: u64) -> SimulationMetrics {
        for _ in 0..num_steps {
            self.step();
        }
        self.last_metrics.clone()
    }

    /// Get the most recent metrics snapshot without advancing the simulation.
    pub fn get_metrics(&self) -> &SimulationMetrics {
        &self.last_metrics
    }

    /// Current simulation time slot.
    pub fn current_slot(&self) -> u64 {
        self.scheduler.current_slot
    }

    /// Estimated simulation time in milliseconds (slot × dt).
    pub fn current_time_ms(&self) -> f64 {
        self.scheduler.current_slot as f64 * self.dt as f64
    }

    /// Read-only reference to the underlying scheduler (for advanced access).
    pub fn scheduler(&self) -> &Scheduler {
        &self.scheduler
    }
}
