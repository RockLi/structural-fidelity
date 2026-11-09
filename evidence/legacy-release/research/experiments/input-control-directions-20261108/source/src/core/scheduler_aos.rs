use crate::core::chunk::{ChunkId, ChunkStatus, DelayedEvent};
use crate::core::chunk_aos::ChunkAoS;
use crate::core::scheduler::SchedulerStepMetrics;
use std::collections::{HashMap, HashSet};

/// A mirror of the Scheduler using AoS chunks.
/// Used for side-by-side performance re-evaluation in Stage 1.2.
pub struct SchedulerAoS {
    pub chunks: HashMap<ChunkId, ChunkAoS>,
    active_chunks: HashSet<ChunkId>,
    pub current_slot: u64,
    pub dt: f32,
}

impl SchedulerAoS {
    pub fn new(dt: f32) -> Self {
        Self {
            chunks: HashMap::new(),
            active_chunks: HashSet::new(),
            current_slot: 0,
            dt,
        }
    }

    pub fn add_chunk(&mut self, chunk: ChunkAoS) {
        let id = chunk.id;
        if chunk.status == ChunkStatus::Active {
            self.active_chunks.insert(id);
        }
        self.chunks.insert(id, chunk);
    }

    pub fn inject_event(&mut self, event: DelayedEvent) {
        if let Some(chunk) = self.chunks.get_mut(&event.target_chunk) {
            chunk.event_queue.push(event);
        }
    }

    pub fn step(&mut self) -> SchedulerStepMetrics {
        let mut metrics = SchedulerStepMetrics::default();
        let slot = self.current_slot;

        let mut wake_ups = Vec::new();
        for (id, chunk) in self.chunks.iter() {
            match chunk.status {
                ChunkStatus::Dormant | ChunkStatus::PendingWakeUp { .. } => {
                    if let Some(next_slot) = chunk.event_queue.next_wake_slot() {
                        if next_slot <= slot {
                            wake_ups.push(*id);
                        }
                    }
                }
                _ => {}
            }
        }

        for id in wake_ups {
            self.active_chunks.insert(id);
        }

        for (id, chunk) in self.chunks.iter_mut() {
            if !self.active_chunks.contains(id) {
                chunk.skip_dormant();
                metrics.dormant_skip_count += 1;
            }
        }

        metrics.active_chunk_count = self.active_chunks.len() as u32;
        let mut still_active = Vec::new();

        for &id in &self.active_chunks {
            if let Some(chunk) = self.chunks.get_mut(&id) {
                let spike_produced = chunk.step(self.dt, slot);
                metrics.total_spikes += chunk.metrics.spikes_last_step;

                if spike_produced || chunk.event_queue.next_wake_slot().is_some() {
                    still_active.push(id);
                }
            }
        }

        let next_active: std::collections::HashSet<ChunkId> = still_active.into_iter().collect();
        self.active_chunks = next_active;
        self.current_slot += 1;
        metrics
    }
}
