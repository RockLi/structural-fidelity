//! LPU Euler update kernel: replaces explicit micro-edge-driven conductances
//! with proxy-channel-driven dynamics.
//!
//! In **LPU mode**, the `g_local_exc` and `g_local_inh` arrays are not driven
//! by per-unit synaptic events but by chunk-level aggregate fields computed by
//! the `LocalFieldAggregator`. The kernel itself remains the same branchless
//! SIMD-friendly Euler update; only the *source* of the conductance changes.
//!
//! # Integration Path
//! The LPU kernel is invoked from `Chunk::step()` when the scheduler operates
//! in LPU mode. In explicit mode, the same `step_euler_simd_friendly()` is used
//! but conductances are pre-filled from explicit edges via `EventRouter`.
//!
//! # State Mapping
//! | Explicit mode                 | LPU mode                             |
//! |-------------------------------|--------------------------------------|
//! | `g_local_exc`: per-unit EPSC  | `g_local_exc`: chunk-level E proxy   |
//! | `g_local_inh`: per-unit IPSC  | `g_local_inh`: chunk-level I proxy   |
//! | `g_long_range`: route input   | `g_long_range`: route input (same)   |
//!
//! All arrays remain at the same SoA layout — only the *fill mechanism* differs.

use crate::lpu::aggregator::AggregatorParams;
use crate::state::ChunkStateArrays;

/// Apply an LPU-mode Euler step: inject proxy drive into conductances, then
/// run the branchless SIMD kernel.
///
/// Unlike the explicit path, where `EventRouter` fills `g_local_exc/inh` from
/// individual synaptic events, here the aggregate drive is computed once per
/// chunk and broadcast uniformly to all units.
///
/// # Arguments
/// - `state`: mutable SoA state for the chunk.
/// - `exc_drive`: aggregate excitatory drive this step (from aggregator).
/// - `inh_drive`: aggregate inhibitory drive this step (from aggregator).
/// - `dt`: simulation timestep.
/// - `current_slot`: current scheduler slot.
/// - `params`: calibrated aggregation parameters.
pub fn step_lpu_euler(
    state: &mut ChunkStateArrays,
    exc_drive: f32,
    inh_drive: f32,
    dt: f32,
    current_slot: u64,
    _params: &AggregatorParams,
) {
    // Broadcast proxy drive to all units (uniform field injection).
    // This replaces the per-edge conductance injection from EventRouter.
    for i in 0..state.num_units {
        state.g_local_exc[i] += exc_drive;
        state.g_local_inh[i] += inh_drive;
    }

    // Run the standard branchless SIMD Euler kernel (unchanged from Phase 1).
    state.step_euler_simd_friendly(dt, current_slot);
}

/// Compute resources saved by LPU mode vs. explicit mode for one step.
///
/// Returns `(events_saved, bytes_avoided)` compared to an explicit baseline
/// that would have injected `explicit_event_count` events of `bytes_per_event` bytes each.
pub fn lpu_resource_delta(explicit_event_count: u32, bytes_per_event: usize) -> (u32, usize) {
    // LPU injects exactly 1 broadcast per chunk vs N explicit events.
    let lpu_events_per_chunk = 1u32;
    let events_saved = explicit_event_count.saturating_sub(lpu_events_per_chunk);
    let bytes_avoided = events_saved as usize * bytes_per_event;
    (events_saved, bytes_avoided)
}
