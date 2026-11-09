//! Local event router: propagates spike output from active chunks into the
//! delayed event queues of target chunks, based on an explicit connectivity map.
//!
//! This is the runtime component that makes explicit connectivity live.
//! After each scheduler step, the router inspects spike output per chunk
//! and injects `DelayedEvent`s into target chunks' queues.
//!
//! # Position in the pipeline
//! ```text
//! Scheduler::step()
//!   → chunk.step() → spike_flags updated
//!   → EventRouter::route_spikes()
//!       → for each spiking chunk, look up outgoing edges
//!       → inject DelayedEvent into target chunk queues
//!   → next Scheduler::step() processes the queue
//! ```

use crate::connectivity::types::{LocalProjection, PopulationType};
use crate::core::chunk::{ChunkId, DelayedEvent};
use crate::core::scheduler::Scheduler;

/// Routable edge in the precomputed adjacency table.
#[derive(Debug, Clone)]
struct RoutableEdge {
    target_chunk: ChunkId,
    source_type: PopulationType,
    weight: f32,
    delay_slots: u64,
}

/// Precomputed adjacency map from source ChunkId → outgoing edges.
///
/// Built once from a set of `LocalProjection`s. At runtime, `route_spikes()`
/// uses this map to inject events without re-scanning the full edge list.
#[derive(Debug, Default)]
pub struct EventRouter {
    /// Adjacency table: index by ChunkId raw value.
    adjacency: Vec<Vec<RoutableEdge>>,
    /// Total edges registered (for resource metrics).
    total_edge_count: usize,
}

impl EventRouter {
    /// Build the router from a slice of projections.
    ///
    /// `num_chunks` must be at least the highest ChunkId + 1 across all edges.
    pub fn from_projections(projections: &[&LocalProjection], num_chunks: usize) -> Self {
        let mut adjacency: Vec<Vec<RoutableEdge>> = vec![Vec::new(); num_chunks];
        let mut total_edge_count = 0;

        for proj in projections {
            for edge in &proj.edges {
                let src_idx = edge.source_chunk.0 as usize;
                if src_idx < num_chunks {
                    adjacency[src_idx].push(RoutableEdge {
                        target_chunk: edge.target_chunk,
                        source_type: edge.source_type,
                        weight: edge.weight,
                        delay_slots: edge.delay_slots,
                    });
                    total_edge_count += 1;
                }
            }
        }

        Self {
            adjacency,
            total_edge_count,
        }
    }

    /// Total edges registered in this router.
    pub fn total_edge_count(&self) -> usize {
        self.total_edge_count
    }

    /// Route spike output from a completed scheduler step.
    ///
    /// For each active chunk, reads its `spike_flags` and, if any unit fired,
    /// injects `DelayedEvent`s into the target chunks defined by the adjacency map.
    ///
    /// `spike_scale` allows normalizing per-chunk spike output to a signal
    /// magnitude (e.g., `spike_sum / num_units` for population firing rate).
    /// Use `1.0` for raw weight-scaled injection.
    pub fn route_spikes(&self, scheduler: &mut Scheduler, spike_scale: f32) {
        let current_slot = scheduler.current_slot;

        // Collect (chunk_id, spike_sum) for all chunks with non-zero spikes.
        // We snapshot before mutating the scheduler to avoid borrow conflicts.
        let mut spiking: Vec<(ChunkId, f32)> = scheduler
            .chunks
            .iter()
            .filter_map(|(&id, chunk)| {
                let spike_sum: f32 = chunk.state.spike_flags.iter().sum();
                if spike_sum > 0.0 {
                    Some((id, spike_sum * spike_scale))
                } else {
                    None
                }
            })
            .collect();

        spiking.sort_by_key(|(id, _)| id.0); // Canonical accumulation order.

        // Inject events into target chunks.
        for (src_id, spike_signal) in spiking {
            let src_idx = src_id.0 as usize;
            if src_idx >= self.adjacency.len() {
                continue;
            }
            for edge in &self.adjacency[src_idx] {
                // Scale the signal by the synaptic weight and spike magnitude.
                // Inhibitory sources invert the sign so the receiving chunk's
                // g_local_inh accumulates (positive) rather than g_long_range.
                let strength = edge.weight * spike_signal;
                scheduler.inject_event(DelayedEvent {
                    target_chunk: edge.target_chunk,
                    target_slot: current_slot + edge.delay_slots,
                    // Use positive signal_strength; the receiving kernel decodes
                    // channel assignment via DelayedEventKind (to be extended in Phase 2.1).
                    // For now, all signals route to g_long_range; the LPU layer
                    // re-routes via LocalFieldAggregator.
                    signal_strength: if edge.source_type == PopulationType::Inhibitory {
                        -strength
                    } else {
                        strength
                    },
                });
            }
        }
    }

    /// Per-step resource metrics: total events injected this step.
    ///
    /// Useful for Task 5 resource accounting across explicit vs. LPU modes.
    pub fn count_injected_events(&self, scheduler: &Scheduler, spike_scale: f32) -> (u32, u32) {
        // Returns (excitatory_events, inhibitory_events) that would be injected.
        let mut exc_count = 0u32;
        let mut inh_count = 0u32;

        for (&id, chunk) in &scheduler.chunks {
            let spike_sum: f32 = chunk.state.spike_flags.iter().sum();
            if spike_sum > 0.0 {
                let src_idx = id.0 as usize;
                if src_idx >= self.adjacency.len() {
                    continue;
                }
                for edge in &self.adjacency[src_idx] {
                    let _ = spike_scale;
                    match edge.source_type {
                        PopulationType::Excitatory => exc_count += 1,
                        PopulationType::Inhibitory => inh_count += 1,
                    }
                }
            }
        }

        (exc_count, inh_count)
    }
}
