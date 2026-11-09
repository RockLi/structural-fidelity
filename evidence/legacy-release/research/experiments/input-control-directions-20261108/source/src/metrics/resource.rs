//! Resource-benefit metrics for Phase 2 Paper 2 comparison (Task 5).
//!
//! Implements both **Global** and **Per-Chunk** resource metrics so that
//! Paper 2 can report savings at the right granularity for the chunk-centric
//! runtime.
//!
//! # Global Metrics
//! - Explicit edge count vs. LPU proxy count
//! - Total events injected (over full run)
//! - Runtime per step (implicit via SchedulerStepMetrics)
//!
//! # Per-Chunk Metrics (Chunk-Centric Accounting)
//! - Per-active-chunk update cost (events handled per chunk per step)
//! - Per-step event traffic: explicit routed events vs. LPU broadcast events
//! - Queue pressure: mean queue depth per active chunk

use crate::connectivity::microcircuit::EIMicrocircuit;
use crate::experiment::harness::RunRecord;

/// Complete resource summary for one execution mode.
#[derive(Debug, Clone)]
pub struct ResourceSummary {
    /// Total explicit edge count (0 for pure LPU mode).
    pub explicit_edge_count: usize,
    /// Total events injected over the full run.
    pub total_events: u64,
    /// Mean events injected per step.
    pub mean_events_per_step: f32,
    /// Mean active chunk count per step.
    pub mean_active_chunks: f32,
    /// Mean events per active chunk per step (per-chunk traffic metric).
    pub mean_events_per_active_chunk: f32,
    /// Total memory used by explicit edges (bytes).
    pub edge_memory_bytes: usize,
}

impl ResourceSummary {
    /// Build a resource summary from a run record and optional microcircuit.
    pub fn from_run(record: &RunRecord, microcircuit: Option<&EIMicrocircuit>) -> Self {
        let total_events = record.total_events();
        let n_steps = record.steps.len().max(1);
        let mean_events_per_step = total_events as f32 / n_steps as f32;
        let mean_active_chunks = record.mean_active_chunks();

        let mean_events_per_active_chunk = if mean_active_chunks > 0.0 {
            mean_events_per_step / mean_active_chunks
        } else {
            0.0
        };

        let (explicit_edge_count, edge_memory_bytes) = microcircuit
            .map(|m| (m.total_edge_count(), m.total_memory_bytes()))
            .unwrap_or((0, 0));

        Self {
            explicit_edge_count,
            total_events,
            mean_events_per_step,
            mean_active_chunks,
            mean_events_per_active_chunk,
            edge_memory_bytes,
        }
    }

    pub fn summary(&self) -> String {
        format!(
            "ResourceSummary: edges={} ({:.1} KB) | events_total={} | \
             events/step={:.1} | active_chunks/step={:.1} | events/chunk/step={:.2}",
            self.explicit_edge_count,
            self.edge_memory_bytes as f64 / 1024.0,
            self.total_events,
            self.mean_events_per_step,
            self.mean_active_chunks,
            self.mean_events_per_active_chunk,
        )
    }
}

/// Full resource comparison between explicit and LPU modes.
#[derive(Debug)]
pub struct ResourceComparison {
    pub explicit: ResourceSummary,
    pub lpu: ResourceSummary,
    /// Relative reduction in total events (0.0 = no saving, 1.0 = 100% saving).
    pub event_reduction_ratio: f32,
    /// Reduction in explicit edge memory (bytes).
    pub edge_memory_saving_bytes: usize,
    /// Reduction in mean events per active chunk per step.
    pub per_chunk_traffic_reduction: f32,
}

impl ResourceComparison {
    /// Compute a full resource comparison from paired run records.
    pub fn compute(
        explicit_record: &RunRecord,
        lpu_record: &RunRecord,
        microcircuit: &EIMicrocircuit,
    ) -> Self {
        let explicit = ResourceSummary::from_run(explicit_record, Some(microcircuit));
        let lpu = ResourceSummary::from_run(lpu_record, None);

        let event_reduction_ratio = if explicit.total_events > 0 {
            1.0 - lpu.total_events as f32 / explicit.total_events as f32
        } else {
            0.0
        };

        let edge_memory_saving_bytes = explicit.edge_memory_bytes;

        let per_chunk_traffic_reduction =
            explicit.mean_events_per_active_chunk - lpu.mean_events_per_active_chunk;

        Self {
            explicit,
            lpu,
            event_reduction_ratio,
            edge_memory_saving_bytes,
            per_chunk_traffic_reduction,
        }
    }

    pub fn summary(&self) -> String {
        format!(
            "ResourceComparison:\n  Explicit: {}\n  LPU:      {}\n  \
             EventReduction={:.1}% | EdgeMemSaved={:.1}KB | PerChunkTrafficDelta={:.2}",
            self.explicit.summary(),
            self.lpu.summary(),
            self.event_reduction_ratio * 100.0,
            self.edge_memory_saving_bytes as f64 / 1024.0,
            self.per_chunk_traffic_reduction,
        )
    }
}

/// Replacement-ratio sweep result for one data point.
#[derive(Debug, Clone)]
pub struct ReplacementRatioPoint {
    /// Fraction of edges replaced by LPU (0.0 = explicit, 1.0 = full LPU).
    pub replacement_ratio: f32,
    /// Firing-rate relative error at this ratio.
    pub firing_rate_error: f32,
    /// Event reduction ratio at this ratio.
    pub event_reduction: f32,
    /// Trajectory correlation at this ratio.
    pub trajectory_correlation: f32,
}

impl ReplacementRatioPoint {
    pub fn header() -> &'static str {
        "ratio | rate_err | event_reduction | traj_corr"
    }

    pub fn row(&self) -> String {
        format!(
            "{:.2}  | {:.4}   | {:.4}          | {:.4}",
            self.replacement_ratio,
            self.firing_rate_error,
            self.event_reduction,
            self.trajectory_correlation,
        )
    }
}

/// Print a formatted sweep table from a set of data points.
pub fn print_sweep_table(points: &[ReplacementRatioPoint]) {
    println!("{}", ReplacementRatioPoint::header());
    println!("{}", "-".repeat(48));
    for p in points {
        println!("{}", p.row());
    }
}
