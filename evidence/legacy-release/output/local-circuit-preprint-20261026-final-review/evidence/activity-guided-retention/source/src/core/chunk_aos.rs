use crate::core::chunk::{
    ChunkContext, ChunkEventQueue, ChunkId, ChunkMetrics, ChunkStatus, GridCoord,
};
use crate::state::aos_baseline::AosStateBaseline;

/// A mirror of the Chunk envelope using AoS state storage.
/// Used for side-by-side performance re-evaluation in Stage 1.2.
#[derive(Debug)]
pub struct ChunkAoS {
    pub id: ChunkId,
    pub coord: GridCoord,
    pub status: ChunkStatus,
    pub state: AosStateBaseline,
    pub context: ChunkContext,
    pub event_queue: ChunkEventQueue,
    pub metrics: ChunkMetrics,
}

impl ChunkAoS {
    pub fn new(id: ChunkId, coord: GridCoord, num_units: usize, field_decay_tau: f32) -> Self {
        Self {
            id,
            coord,
            status: ChunkStatus::Active,
            state: AosStateBaseline::new(num_units),
            context: ChunkContext::new(field_decay_tau),
            event_queue: ChunkEventQueue::default(),
            metrics: ChunkMetrics::default(),
        }
    }

    pub fn step(&mut self, dt: f32, current_slot: u64) -> bool {
        let due_events = self.event_queue.drain_due(current_slot);
        for event in &due_events {
            for neuron in self.state.units.iter_mut() {
                neuron.g_long_range += event.signal_strength;
            }
        }

        let exc_field = self.context.local_exc_field;
        let inh_field = self.context.local_inh_field;
        for neuron in self.state.units.iter_mut() {
            neuron.g_local_exc += exc_field * 0.01;
            neuron.g_local_inh += inh_field * 0.01;
        }

        self.state.step_euler(dt, current_slot);

        let spike_sum: f32 = self.state.units.iter().map(|n| n.spike_flag).sum();
        self.context.update_fields(spike_sum, dt);

        self.metrics.spikes_last_step = spike_sum as u32;
        self.metrics.active_step_count += 1;

        // Determine next status (same logic as Chunk::step — see that function for rationale).
        const DYNAMICS_EPSILON: f32 = 1e-6;
        let is_active = spike_sum > 0.0
            || !due_events.is_empty()
            || self.context.is_dynamics_active(DYNAMICS_EPSILON)
            || self.state.has_active_conductance(DYNAMICS_EPSILON);

        self.status = match self.event_queue.next_wake_slot() {
            Some(wake_slot) if !is_active => ChunkStatus::PendingWakeUp { wake_slot },
            _ if is_active => ChunkStatus::Active,
            _ => ChunkStatus::Dormant,
        };

        is_active
    }

    pub fn skip_dormant(&mut self) {
        self.metrics.dormant_skip_count += 1;
    }
}
