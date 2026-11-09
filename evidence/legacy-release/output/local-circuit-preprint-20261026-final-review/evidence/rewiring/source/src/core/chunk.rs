use crate::state::ChunkStateArrays;

/// Unique identifier for a chunk in the spatial grid.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ChunkId(pub u32);

/// 3D spatial grid coordinate for a chunk.
#[derive(Debug, Clone, Copy)]
pub struct GridCoord {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

/// Lifecycle status of a chunk in the scheduler.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChunkStatus {
    /// Chunk has active units or pending events. Must be stepped this slot.
    Active,
    /// Chunk is dormant. May be skipped unless a wake-up event arrives.
    Dormant,
    /// Chunk has a pending delayed event arriving in a future slot.
    PendingWakeUp { wake_slot: u64 },
}

/// Runtime metrics collected per chunk per step.
#[derive(Debug, Default, Clone)]
pub struct ChunkMetrics {
    /// Number of spikes fired in the last step.
    pub spikes_last_step: u32,
    /// Number of times this chunk has been dormant-skipped since last activation.
    pub dormant_skip_count: u64,
    /// Total steps this chunk has been active.
    pub active_step_count: u64,
}

/// Shared chunk-level context: local field aggregates.
///
/// Local excitatory and inhibitory field values are derived from spike
/// activity within the chunk and broadcast to individual unit channels
/// in the SoA state arrays. These replace explicit dense local edges
/// in the LPU-compatible substrate.
#[derive(Debug, Default)]
pub struct ChunkContext {
    /// Aggregate excitatory field over the chunk (normalized spike rate).
    pub local_exc_field: f32,
    /// Aggregate inhibitory field over the chunk (normalized spike rate).
    pub local_inh_field: f32,
    /// Time decay constant for field aggregation.
    pub field_decay_tau: f32,
}

impl ChunkContext {
    pub fn new(field_decay_tau: f32) -> Self {
        Self {
            local_exc_field: 0.0,
            local_inh_field: 0.0,
            field_decay_tau,
        }
    }

    /// Update local fields after a step based on observed spike output.
    pub fn update_fields(&mut self, spike_sum: f32, dt: f32) {
        let decay = (-dt / self.field_decay_tau).exp();
        self.local_exc_field = self.local_exc_field * decay + spike_sum;
        // Inhibitory field decays symmetrically; it has no additive spike source
        // at this stage — it is driven externally or by future inhibitory populations.
        self.local_inh_field *= decay;
    }

    /// Returns `true` if local field state has significant residual dynamics.
    ///
    /// Used by `Chunk::step()` to prevent premature dormancy when subthreshold
    /// events have elevated the local field without triggering a spike.
    /// `epsilon` is the magnitude below which a field value is treated as zero.
    #[inline]
    pub fn is_dynamics_active(&self, epsilon: f32) -> bool {
        self.local_exc_field.abs() > epsilon || self.local_inh_field.abs() > epsilon
    }
}

/// Minimal delayed event entry: activates a chunk at a future time slot.
#[derive(Debug, Clone)]
pub struct DelayedEvent {
    pub target_chunk: ChunkId,
    pub target_slot: u64,
    /// Incoming signal strength (e.g., from a route landing).
    pub signal_strength: f32,
}

/// Slot-based delayed event queue for a chunk.
/// Stores events to be delivered at future simulation steps.
#[derive(Debug, Default)]
pub struct ChunkEventQueue {
    pending: Vec<DelayedEvent>,
}

impl ChunkEventQueue {
    /// Enqueue a delayed event.
    pub fn push(&mut self, event: DelayedEvent) {
        self.pending.push(event);
    }

    /// Drain all events due at or before `current_slot`.
    pub fn drain_due(&mut self, current_slot: u64) -> Vec<DelayedEvent> {
        let (due, future): (Vec<_>, Vec<_>) = self
            .pending
            .drain(..)
            .partition(|e| e.target_slot <= current_slot);
        self.pending = future;
        due
    }

    /// Returns the earliest pending wake-up slot, if any.
    pub fn next_wake_slot(&self) -> Option<u64> {
        self.pending.iter().map(|e| e.target_slot).min()
    }

    /// Count how many events are due at or before `current_slot`.
    ///
    /// Used by the scheduler instrumentation to accurately report
    /// `event_count` even when a chunk has multiple co-due events.
    pub fn count_due(&self, current_slot: u64) -> u32 {
        self.pending
            .iter()
            .filter(|e| e.target_slot <= current_slot)
            .count() as u32
    }
}

/// The Chunk envelope — the minimal unit of state ownership and scheduling.
///
/// A chunk owns its SoA state arrays, event queue, context fields, and status.
/// It is the atomic unit for scheduling decisions, memory residency, and
/// future route landing.
#[derive(Debug)]
pub struct Chunk {
    pub id: ChunkId,
    pub coord: GridCoord,
    pub status: ChunkStatus,
    pub state: ChunkStateArrays,
    pub context: ChunkContext,
    pub event_queue: ChunkEventQueue,
    pub metrics: ChunkMetrics,
}

impl Chunk {
    /// Create a new chunk at the given grid coordinate with `num_units` units.
    pub fn new(id: ChunkId, coord: GridCoord, num_units: usize, field_decay_tau: f32) -> Self {
        Self {
            id,
            coord,
            status: ChunkStatus::Active,
            state: ChunkStateArrays::new(num_units),
            context: ChunkContext::new(field_decay_tau),
            event_queue: ChunkEventQueue::default(),
            metrics: ChunkMetrics::default(),
        }
    }

    /// Step the chunk state forward by one slot.
    /// Returns `true` if the chunk produced any spikes (remains active).
    pub fn step(&mut self, dt: f32, current_slot: u64) -> bool {
        // Process any due delayed events, routing by sign into the correct channel:
        //   signal_strength > 0  →  excitatory (E→E or E→I): inject into g_local_exc
        //   signal_strength < 0  →  inhibitory (I→E or I→I): inject abs value into g_local_inh
        //   signal_strength == 0 →  no-op (pure wake-up events from InputProtocol)
        //
        // i_syn = g_local_exc - g_local_inh + g_long_range (membrane kernel convention).
        // Do NOT also write into g_long_range: that would cancel inhibitory events
        // (−g_local_inh + g_long_range = 0) and double-count excitatory ones.
        // Dormancy keep-alive is handled by the event_queue having pending events.
        let due_events = self.event_queue.drain_due(current_slot);
        for event in &due_events {
            if event.signal_strength > 0.0 {
                // Excitatory local micro-edge or external tonic drive.
                for g in self.state.g_local_exc.iter_mut() {
                    *g += event.signal_strength;
                }
            } else if event.signal_strength < 0.0 {
                // Inhibitory local micro-edge: inject absolute value into inh channel.
                let inh = -event.signal_strength;
                for g in self.state.g_local_inh.iter_mut() {
                    *g += inh;
                }
            }
            // Zero-strength events are pure wake-ups; no conductance update needed.
        }

        // Propagate local chunk fields into per-unit channels.
        let exc_field = self.context.local_exc_field;
        let inh_field = self.context.local_inh_field;
        for i in 0..self.state.num_units {
            self.state.g_local_exc[i] += exc_field * 0.01;
            self.state.g_local_inh[i] += inh_field * 0.01;
        }

        // Run SoA Euler update (branchless / SIMD-friendly kernel).
        self.state.step_euler_simd_friendly(dt, current_slot);

        // Aggregate spike output back into context fields.
        let spike_sum: f32 = self.state.spike_flags.iter().sum();
        self.context.update_fields(spike_sum, dt);

        // Update metrics.
        self.metrics.spikes_last_step = spike_sum as u32;
        self.metrics.active_step_count += 1;

        // Determine next status.
        //
        // A chunk must remain Active if ANY of the following hold:
        //   (a) spike_sum > 0   — units fired; downstream must integrate
        //   (b) event arrived   — conductances were just injected
        //   (c) local fields hot — subthreshold exc/inh still decaying in context
        //   (d) long-range conductance hot — injected g_long_range not yet decayed
        //
        // Without (c) and (d) a subthreshold event causes the chunk to go Dormant
        // on the next slot, truncating the conductance and voltage decay tails.
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

    /// Mark this chunk as dormant-skipped (no step taken).
    pub fn skip_dormant(&mut self) {
        self.metrics.dormant_skip_count += 1;
    }

    /// Total memory in bytes used by this chunk's state arrays.
    pub fn state_memory_bytes(&self) -> usize {
        self.state.memory_bytes()
    }
}
