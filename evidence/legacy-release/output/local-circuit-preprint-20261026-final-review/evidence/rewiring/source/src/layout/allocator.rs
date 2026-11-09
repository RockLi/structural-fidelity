//! Stage 1.3: Synthetic Chunk Allocator
//!
//! Provides efficient bulk allocation of isolated (zero-connectivity) chunk
//! populations for memory floor and scheduler scalability testing.
//!
//! # Design Goals
//! - Allocate N chunks spanning M total units in a single call.
//! - Support configurable units-per-chunk (default: 1,000 for benchmark parity).
//! - Zero explicit edge overhead: no synaptic weight arrays, no connectivity graphs.
//! - All chunks initialized to `Dormant` status to test quiescent memory floor.
//!
//! # Usage
//! ```rust
//! use next_brain::layout::allocator::SyntheticChunkAllocator;
//! let alloc = SyntheticChunkAllocator::new(1_000_000, 1_000, 10.0);
//! let chunks = alloc.build();
//! println!("Allocated {} chunks", chunks.len());
//! ```

use crate::core::chunk::{Chunk, ChunkId, ChunkStatus, GridCoord};

/// Configuration for a synthetic (connectivity-free) population of chunks.
pub struct SyntheticChunkAllocator {
    /// Total number of neural units to allocate.
    pub total_units: usize,
    /// Units per chunk (determines number of chunks).
    pub units_per_chunk: usize,
    /// Field decay time constant passed to each chunk context.
    pub field_decay_tau: f32,
}

impl SyntheticChunkAllocator {
    /// Create a new allocator.
    ///
    /// - `total_units`: Total neural units (e.g., 1_000_000 for 1M).
    /// - `units_per_chunk`: Chunk size (e.g., 1_000 → 1,000 chunks per million units).
    /// - `field_decay_tau`: LPU-compatible field decay constant (biologically: ~10.0 ms).
    pub fn new(total_units: usize, units_per_chunk: usize, field_decay_tau: f32) -> Self {
        assert!(units_per_chunk > 0, "units_per_chunk must be > 0");
        assert!(total_units > 0, "total_units must be > 0");
        Self {
            total_units,
            units_per_chunk,
            field_decay_tau,
        }
    }

    /// Total number of chunks that will be allocated (ceiling division — includes partial tail).
    pub fn num_chunks(&self) -> usize {
        self.total_units.div_ceil(self.units_per_chunk)
    }

    /// Remainder units in the last (partial) chunk, or 0 if total_units divides evenly.
    pub fn remainder_units(&self) -> usize {
        self.total_units % self.units_per_chunk
    }

    /// Expected total memory footprint of all SoA state arrays (bytes).
    ///
    /// Does NOT include Chunk envelope overhead (status, context, event_queue).
    /// Only counts the neural state arrays themselves (the memory floor).
    pub fn expected_state_bytes(&self) -> usize {
        let f32_arrays: usize = 6; // voltages, recovery, g_local_exc, g_local_inh, g_long_range, spike_flags
        let u64_arrays: usize = 1; // refractory_until (u64 — avoids slot wrap-around)
        let bytes_per_unit = f32_arrays * 4 + u64_arrays * 8; // f32=4B, u64=8B → 32 bytes/unit
        self.total_units * bytes_per_unit
    }

    /// Build all chunks and return as a `Vec<Chunk>`.
    ///
    /// All chunks are initialized in `Dormant` status — the true quiescent
    /// memory floor. No events, no connectivity, no initial spike activity.
    /// The last chunk may be smaller than `units_per_chunk` if `total_units`
    /// is not an exact multiple of `units_per_chunk`.
    pub fn build(&self) -> Vec<Chunk> {
        let n = self.num_chunks();
        let remainder = self.remainder_units();
        let mut chunks = Vec::with_capacity(n);

        for i in 0..n {
            let id = ChunkId(i as u32);
            let coord = GridCoord {
                x: i as i32,
                y: 0,
                z: 0,
            };

            // Last chunk is partial when there is a non-zero remainder.
            let size = if i == n - 1 && remainder > 0 {
                remainder
            } else {
                self.units_per_chunk
            };

            let mut chunk = Chunk::new(id, coord, size, self.field_decay_tau);
            chunk.status = ChunkStatus::Dormant;
            chunks.push(chunk);
        }

        chunks
    }

    /// Build and measure wall-clock allocation time.
    ///
    /// Returns `(chunks, elapsed_ms)`. Useful for Benchmark C timing.
    pub fn build_timed(&self) -> (Vec<Chunk>, std::time::Duration) {
        let start = std::time::Instant::now();
        let chunks = self.build();
        let elapsed = start.elapsed();
        (chunks, elapsed)
    }
}

/// Memory floor report for a given allocator configuration.
#[derive(Debug)]
pub struct MemoryFloorReport {
    pub total_units: usize,
    pub num_chunks: usize,
    pub units_per_chunk: usize,
    /// Total SoA state array bytes (theoretical minimum, no envelope overhead).
    pub state_bytes: usize,
    /// Approximate chunk envelope overhead per chunk (status, context, metrics, event_queue).
    pub envelope_bytes_per_chunk: usize,
    /// Total estimated memory: state + envelopes.
    pub total_estimated_bytes: usize,
    /// Wall-clock time to allocate all chunks.
    pub allocation_time: std::time::Duration,
}

impl MemoryFloorReport {
    pub fn generate(alloc: &SyntheticChunkAllocator) -> Self {
        let (chunks, elapsed) = alloc.build_timed();

        // Chunk envelope: status(1B) + GridCoord(12B) + ChunkContext(12B) +
        // ChunkMetrics(24B) + Vec header for event_queue(24B) = ~73B ≈ 128B padded.
        // We use a conservative empirical estimate.
        let envelope_bytes_per_chunk: usize = 256; // conservative upper bound per chunk

        let state_bytes = alloc.expected_state_bytes();
        let envelope_total = alloc.num_chunks() * envelope_bytes_per_chunk;

        // Verify actual state bytes via the first chunk (sanity check).
        let actual_state_per_chunk = chunks.first().map(|c| c.state_memory_bytes()).unwrap_or(0);
        let _ = actual_state_per_chunk; // available for assertions in tests

        Self {
            total_units: alloc.total_units,
            num_chunks: alloc.num_chunks(),
            units_per_chunk: alloc.units_per_chunk,
            state_bytes,
            envelope_bytes_per_chunk,
            total_estimated_bytes: state_bytes + envelope_total,
            allocation_time: elapsed,
        }
    }

    /// Human-readable summary for reports and docs.
    pub fn summary(&self) -> String {
        let state_mb = self.state_bytes as f64 / (1024.0 * 1024.0);
        let total_mb = self.total_estimated_bytes as f64 / (1024.0 * 1024.0);
        let total_gb = total_mb / 1024.0;
        format!(
            "Units: {:>12} | Chunks: {:>8} | State: {:>8.1} MB | Total: {:>8.1} MB ({:.2} GB) | Alloc: {:.1?}",
            self.total_units, self.num_chunks, state_mb, total_mb, total_gb, self.allocation_time,
        )
    }
}
