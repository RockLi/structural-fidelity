use crate::core::chunk::{Chunk, ChunkId, ChunkStatus, DelayedEvent};
use std::collections::{HashMap, HashSet};

/// The core event-driven scheduler responsible for managing chunk life cycles
/// and execution throughput.
pub struct Scheduler {
    /// All chunks owned by this scheduler.
    pub chunks: HashMap<ChunkId, Chunk>,
    /// Indices of chunks that are currently active.
    active_chunks: HashSet<ChunkId>,
    /// Current simulation time in steps (slots).
    pub current_slot: u64,
    /// Timestep delta for Euler updates.
    pub dt: f32,
}

impl Scheduler {
    /// Create a new scheduler with a global timestep.
    pub fn new(dt: f32) -> Self {
        Self {
            chunks: HashMap::new(),
            active_chunks: HashSet::new(),
            current_slot: 0,
            dt,
        }
    }

    /// Add a chunk to the scheduler.
    pub fn add_chunk(&mut self, chunk: Chunk) {
        let id = chunk.id;
        if chunk.status == ChunkStatus::Active {
            self.active_chunks.insert(id);
        }
        self.chunks.insert(id, chunk);
    }

    /// Inject a delayed activation event into the system.
    /// This is the primary mechanism for external stimulus or cross-chunk interaction.
    pub fn inject_event(&mut self, event: DelayedEvent) {
        if let Some(chunk) = self.chunks.get_mut(&event.target_chunk) {
            chunk.event_queue.push(event);

            // If the chunk was dormant but now has events, it might need status update.
            // We'll let the next step cycle handle the transition for efficiency,
            // or we could check immediately. For Benchmark B isolation, we'll check status
            // during the 'tick' phase.
        }
    }

    /// Advance the simulation by a single time slot.
    ///
    /// The pipeline:
    /// 1. Identify chunks that must wake up due to pending events.
    /// 2. Update all active chunks (including those just woken up).
    /// 3. Update the global active set based on spike activity and remaining events.
    ///
    /// Returns [`SchedulerStepMetrics`] with full observability data for scientific
    /// instrumentation (event counts, wake-up rates, stage timings).
    pub fn step(&mut self) -> SchedulerStepMetrics {
        let step_start = std::time::Instant::now();
        let mut metrics = SchedulerStepMetrics::default();
        let slot = self.current_slot;

        // ── Phase 1: Wake-up scan ─────────────────────────────────────────────
        let phase1_start = std::time::Instant::now();
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
        metrics.wakeup_count = wake_ups.len() as u32;
        metrics.phase_wakeup_us = phase1_start.elapsed().as_micros() as u64;

        // Add wake-ups to active set.
        for id in wake_ups {
            self.active_chunks.insert(id);
        }

        // ── Phase 2: Dormant skip scan ────────────────────────────────────────
        let phase2_start = std::time::Instant::now();
        for (id, chunk) in self.chunks.iter_mut() {
            if !self.active_chunks.contains(id) {
                chunk.skip_dormant();
                metrics.dormant_skip_count += 1;
            }
        }
        metrics.phase_dormant_us = phase2_start.elapsed().as_micros() as u64;

        // ── Phase 3: Active chunk update ──────────────────────────────────────
        let phase3_start = std::time::Instant::now();
        metrics.active_chunk_count = self.active_chunks.len() as u32;
        let mut still_active = Vec::new();
        let mut total_events_processed: u32 = 0;

        for &id in &self.active_chunks {
            if let Some(chunk) = self.chunks.get_mut(&id) {
                // Count ALL events due this slot before step() drains them.
                // Previously used next_wake_slot() which could only detect 0 or 1,
                // under-reporting when multiple events share the same due slot.
                total_events_processed += chunk.event_queue.count_due(slot);

                let spike_produced = chunk.step(self.dt, slot);
                metrics.total_spikes += chunk.metrics.spikes_last_step;

                if spike_produced || chunk.event_queue.next_wake_slot().is_some() {
                    still_active.push(id);
                }
            }
        }
        metrics.event_count = total_events_processed;
        metrics.phase_chunk_update_us = phase3_start.elapsed().as_micros() as u64;

        // ── Phase 4: Active-set rebuild ───────────────────────────────────────
        let phase4_start = std::time::Instant::now();
        // O(n) rebuild avoids O(n*m) retain on the previous HashSet.
        let next_active: HashSet<ChunkId> = still_active.into_iter().collect();
        self.active_chunks = next_active;
        metrics.phase_set_rebuild_us = phase4_start.elapsed().as_micros() as u64;

        self.current_slot += 1;
        metrics.step_duration_us = step_start.elapsed().as_micros() as u64;
        metrics
    }
}

/// Consolidated metrics for a single scheduler step.
///
/// Covers all observability dimensions required by the Phase 1 blueprint:
/// - **Active/dormant accounting**: `active_chunk_count`, `dormant_skip_count`
/// - **Event flow**: `event_count` (due events processed), `wakeup_count` (dormant→active)
/// - **Spike output**: `total_spikes`
/// - **Timing breakdown**: per-phase wall-clock durations + total step duration
///
/// All timing fields use microseconds (µs) to stay in the benchmark-relevant range
/// without floating-point overhead.
#[derive(Debug, Default, Clone)]
pub struct SchedulerStepMetrics {
    // ── Activity ──────────────────────────────────────────────────────────────
    /// Number of chunks that were active (stepped) this slot.
    pub active_chunk_count: u32,
    /// Number of chunks that were dormant (skipped) this slot.
    pub dormant_skip_count: u32,
    /// Total spikes emitted across all active chunks.
    pub total_spikes: u32,

    // ── Event flow ────────────────────────────────────────────────────────────
    /// Delayed events that came due and were processed this slot.
    pub event_count: u32,
    /// Chunks that transitioned from Dormant/PendingWakeUp → Active.
    pub wakeup_count: u32,

    // ── Per-phase timing (µs) ─────────────────────────────────────────────────
    /// Time spent in wake-up scan (Phase 1).
    pub phase_wakeup_us: u64,
    /// Time spent skipping dormant chunks (Phase 2).
    pub phase_dormant_us: u64,
    /// Time spent stepping active chunks (Phase 3).
    pub phase_chunk_update_us: u64,
    /// Time spent rebuilding the active-chunk set (Phase 4).
    pub phase_set_rebuild_us: u64,
    /// Total wall-clock time for the entire step (µs).
    pub step_duration_us: u64,
}

impl SchedulerStepMetrics {
    /// One-line summary for logging / scientific reporting.
    ///
    /// Format: `[slot=N] active=A dormant=D wakeup=W events=E spikes=S total=Tµs`
    pub fn summary(&self, slot: u64) -> String {
        format!(
            "[slot={:>8}] active={:>6}  dormant_skip={:>8}  wakeup={:>4}  \
             events={:>6}  spikes={:>8}  step={}µs  (wu={}µs|skip={}µs|upd={}µs|set={}µs)",
            slot,
            self.active_chunk_count,
            self.dormant_skip_count,
            self.wakeup_count,
            self.event_count,
            self.total_spikes,
            self.step_duration_us,
            self.phase_wakeup_us,
            self.phase_dormant_us,
            self.phase_chunk_update_us,
            self.phase_set_rebuild_us,
        )
    }
}
