//! Block-SoA (Blocked Structure of Arrays) neural state layout.
//!
//! # Motivation
//! Standard SoA (`ChunkStateArrays`) stores each field as a single flat array
//! spanning all N units. For a chunk of 1,000 units the `voltages` array alone
//! takes 4 kB — one contiguous region that the CPU must stream end-to-end even
//! when only a small "local patch" of units fires together.
//!
//! Block-SoA partitions the N units into fixed-size **blocks** of `BLOCK_SIZE`
//! units. Within each block all f32 fields are stored contiguously:
//!
//! ```text
//! Block 0: [v0..v7][r0..r7][exc0..exc7][inh0..inh7][lr0..lr7][sf0..sf7]
//! Block 1: [v8..v15]...
//! ```
//!
//! This keeps the full state of `BLOCK_SIZE` units inside 1–2 cache lines, which
//! benefits workloads where activity is spatially clustered (the "local dynamical
//! patch" model). It is the third comparison arm in Benchmark A alongside AoS and
//! standard SoA.
//!
//! # Memory layout constants
//! - `BLOCK_SIZE`: number of units per block. Default: 8 (fits in a single AVX2
//!   register lane for f32 operations).
//! - `F32_FIELDS`: 6 (voltages, recovery, g_local_exc, g_local_inh, g_long_range,
//!   spike_flags).  
//! - `F32_STRIDE`: `BLOCK_SIZE × F32_FIELDS` — f32 elements per block in `f32_data`.
//! - Refractory is stored separately in `refractory_until: Vec<u64>` (flat, not
//!   blocked) to avoid mixing f32/u64 alignment in a single buffer.

/// Number of units packed into one Block-SoA block.
/// 8 = one AVX2 lane width for f32; change to 16 for AVX-512 experiments.
pub const BLOCK_SIZE: usize = 8;

/// Number of f32 state fields per unit.
const F32_FIELDS: usize = 6; // voltages, recovery, g_local_exc, g_local_inh, g_long_range, spike_flags

/// f32 elements per block in the flat buffer.
const F32_STRIDE: usize = BLOCK_SIZE * F32_FIELDS;

// Field offsets within a block (in f32 units, relative to block start).
const OFF_V: usize = 0;
const OFF_R: usize = BLOCK_SIZE;
const OFF_EXC: usize = BLOCK_SIZE * 2;
const OFF_INH: usize = BLOCK_SIZE * 3;
const OFF_LR: usize = BLOCK_SIZE * 4;
const OFF_SF: usize = BLOCK_SIZE * 5;

/// Block-SoA state storage.
///
/// `f32_data`: flat buffer. Block `b`, field offset `off`, unit `i` within block →
/// `f32_data[b * F32_STRIDE + off + i]`.
///
/// `refractory_until`: flat `u64` array indexed directly as `[unit_index]`
/// (not blocked) to avoid mixed-alignment packing complexity.
#[derive(Debug)]
pub struct BlockSoaState {
    /// Total units (may be less than `num_blocks * BLOCK_SIZE` if not aligned).
    pub num_units: usize,
    /// Number of full-or-partial blocks.
    pub num_blocks: usize,
    /// Flat blocked f32 buffer: `[block0_fields | block1_fields | ...]`.
    pub f32_data: Vec<f32>,
    /// Refractory expiry slot per unit (flat, u64).
    pub refractory_until: Vec<u64>,
}

impl BlockSoaState {
    /// Allocate a new `BlockSoaState` for `num_units` units.
    ///
    /// Pads to a multiple of `BLOCK_SIZE` internally; the pad units are
    /// initialized to resting state and never produce spikes.
    pub fn new(num_units: usize) -> Self {
        // Ceiling-divide for the number of blocks (may have a partial tail).
        let num_blocks = num_units.div_ceil(BLOCK_SIZE);
        let padded = num_blocks * BLOCK_SIZE; // total slots including padding

        // Build the flat buffer block by block.
        // voltages = -65.0 (resting), all others = 0.0.
        let mut f32_data = vec![0.0_f32; num_blocks * F32_STRIDE];
        for b in 0..num_blocks {
            let base = b * F32_STRIDE + OFF_V;
            for i in 0..BLOCK_SIZE {
                f32_data[base + i] = -65.0;
            }
        }

        Self {
            num_units,
            num_blocks,
            f32_data,
            refractory_until: vec![0_u64; padded],
        }
    }

    /// Apply one Euler update step across all units (branchless, block-local).
    ///
    /// Same kernel semantics as `ChunkStateArrays::step_euler_simd_friendly`
    /// but iterates block by block so the entire unit state for `BLOCK_SIZE`
    /// units is resident in cache during the inner loop.
    pub fn step_euler(&mut self, dt: f32, current_step: u64) {
        let v_thresh = 30.0_f32;
        let v_reset = -65.0_f32;

        for b in 0..self.num_blocks {
            let base_f32 = b * F32_STRIDE;
            let base_u64 = b * BLOCK_SIZE;

            // Unit count for this block (tail block may be smaller).
            let block_units = (self.num_units - b * BLOCK_SIZE).min(BLOCK_SIZE);

            for i in 0..block_units {
                // --- refractory gate (branchless) ---
                let active_u32 = (self.refractory_until[base_u64 + i] <= current_step) as u32;
                let active = active_u32 as f32;

                // --- field pointers within this block ---
                let bv = base_f32 + OFF_V + i;
                let br = base_f32 + OFF_R + i;
                let be = base_f32 + OFF_EXC + i;
                let bi = base_f32 + OFF_INH + i;
                let bl = base_f32 + OFF_LR + i;
                let bs = base_f32 + OFF_SF + i;

                let i_syn = (self.f32_data[be] - self.f32_data[bi] + self.f32_data[bl]) * active;
                self.f32_data[bv] += (-self.f32_data[bv] + i_syn) * dt * active;

                // Match scalar semantics: refractory units skip the full update.
                let decay = 1.0_f32 - dt * active;
                self.f32_data[be] *= decay;
                self.f32_data[bi] *= decay;
                self.f32_data[bl] *= decay;
                let _ = br; // recovery unused in Phase 1 LIF kernel

                // --- branchless spike + reset ---
                let fired = ((self.f32_data[bv] >= v_thresh) as u32) * active_u32;
                let fired_f = fired as f32;
                self.f32_data[bv] = fired_f * v_reset + (1.0 - fired_f) * self.f32_data[bv];
                self.f32_data[bs] = fired_f;
                self.refractory_until[base_u64 + i] = fired as u64 * (current_step + 2)
                    + (1 - fired as u64) * self.refractory_until[base_u64 + i];
            }
        }
    }

    /// Returns total memory footprint in bytes (f32 buffer + u64 refractory).
    pub fn memory_bytes(&self) -> usize {
        self.f32_data.len() * std::mem::size_of::<f32>()
            + self.refractory_until.len() * std::mem::size_of::<u64>()
    }
}
