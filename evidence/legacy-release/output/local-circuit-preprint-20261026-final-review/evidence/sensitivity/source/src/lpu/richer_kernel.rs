//! Phase 3 Richer Proxy Euler Kernel.
//!
//! Applies the four-channel proxy drive to a chunk's SoA state arrays,
//! then runs the standard SIMD-friendly Euler update.
//!
//! # Relationship to Phase 2 Kernel
//! `step_lpu_euler` (Phase 2) broadcasts a single `(exc_drive, inh_drive)` pair
//! uniformly across all units.  This kernel does the same, but the drive values
//! come from the richer per-channel state accumulated in `RicherProxyState`
//! rather than from a single stateless aggregation step.
//!
//! The drive injection path (`g_local_exc[i] += exc; g_local_inh[i] += inh`)
//! is identical — only the *source* of the drive values differs.

use crate::lpu::proxy_params::RicherProxyState;
use crate::state::ChunkStateArrays;

/// Apply the four-channel richer-proxy drive to a chunk and then advance it
/// one Euler step.
///
/// # Arguments
/// - `state`: mutable SoA arrays for the target chunk.
/// - `proxy_state`: running channel values for this chunk (updated externally
///   by `update_richer_state` before this kernel runs).
/// - `dt`: simulation timestep (ms).
/// - `current_slot`: current scheduler slot (passed through to the Euler kernel).
pub fn step_richer_lpu_euler(
    state: &mut ChunkStateArrays,
    proxy_state: &RicherProxyState,
    dt: f32,
    current_slot: u64,
) {
    let exc_drive = proxy_state.exc_drive();
    let inh_drive = proxy_state.inh_drive();

    // Broadcast proxy drive uniformly (same approach as Phase 2 kernel,
    // only the origin of exc_drive / inh_drive differs).
    for i in 0..state.num_units {
        state.g_local_exc[i] += exc_drive;
        state.g_local_inh[i] += inh_drive;
    }

    // Advance the standard branchless SIMD-friendly Euler kernel.
    state.step_euler_simd_friendly(dt, current_slot);
}
