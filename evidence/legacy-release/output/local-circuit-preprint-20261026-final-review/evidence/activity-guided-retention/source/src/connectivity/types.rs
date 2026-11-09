//! Core types for Phase 2 explicit local connectivity.
//!
//! These types represent the **explicit micro-edge baseline** required by
//! Paper 2: a minimal static E/I microcircuit that can be compared against
//! the LPU-replaced execution path.

use crate::core::chunk::ChunkId;

/// Broad class of a neuron population: excitatory or inhibitory.
///
/// Used to determine aggregation channels (E → g_local_exc, I → g_local_inh)
/// and to split populations during microcircuit construction.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PopulationType {
    Excitatory,
    Inhibitory,
}

/// A single static synaptic edge from a source chunk to a target chunk.
///
/// Phase 2 uses **fixed-weight, fixed-delay** edges to keep the explicit
/// baseline simple and controlled. No plasticity, no dynamic routing.
///
/// The edge carries a signal from the `source_chunk` to the `target_chunk`.
/// The signal strength is applied to the appropriate conductance channel of
/// all units in the target chunk (E→g_local_exc, I→g_local_inh).
#[derive(Debug, Clone)]
pub struct SynapticEdge {
    /// Source chunk (where spikes originate).
    pub source_chunk: ChunkId,
    /// Target chunk (where signals are injected).
    pub target_chunk: ChunkId,
    /// Source population type (determines which channel the signal enters).
    pub source_type: PopulationType,
    /// Fixed synaptic weight / signal strength.
    pub weight: f32,
    /// Propagation delay in scheduler slots.
    pub delay_slots: u64,
}

impl SynapticEdge {
    /// Create a new synaptic edge.
    pub fn new(
        source_chunk: ChunkId,
        target_chunk: ChunkId,
        source_type: PopulationType,
        weight: f32,
        delay_slots: u64,
    ) -> Self {
        Self {
            source_chunk,
            target_chunk,
            source_type,
            weight,
            delay_slots,
        }
    }
}

/// A projection: a named, typed set of synaptic edges between two chunk ranges.
///
/// Represents one arm of the E/I microcircuit (e.g., E→I recurrent projection).
/// The projection carries metadata for resource accounting in Paper 2 metrics.
#[derive(Debug, Clone)]
pub struct LocalProjection {
    /// Label for this projection arm (e.g., "E→I_recurrent").
    pub label: String,
    /// Source population type.
    pub source_type: PopulationType,
    /// All edges in this projection.
    pub edges: Vec<SynapticEdge>,
}

impl LocalProjection {
    /// Number of explicit edges in this projection.
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    /// Total memory used by this projection's edge list (bytes).
    pub fn memory_bytes(&self) -> usize {
        // SynapticEdge: 2×u32 (ChunkIds) + 1×u32 (PopulationType tag) + 1×f32 + 1×u64
        // = 8 + 4 + 4 + 8 = 24 bytes per edge (aligned)
        self.edges.len() * std::mem::size_of::<SynapticEdge>()
    }

    /// Splits this projection into two subsets: explicitly kept and LPU-replaced.
    ///
    /// - `replace_ratio`: fraction of edges to route via LPU proxy (0.0 = all explicit, 1.0 = all LPU)
    /// - `seed`: RNG seed to ensure deterministic structural split.
    ///
    /// The edges are shuffled before splitting to prevent structural anisotropy
    /// (e.g. keeping all edges from lower Chunk IDs and discarding higher ones).
    pub fn split(&self, replace_ratio: f32, seed: u64) -> (LocalProjection, LocalProjection) {
        let mut edges = self.edges.clone();
        let mut rng = crate::connectivity::microcircuit::LcgRng::new(seed);

        // Deterministic Fisher-Yates shuffle
        for i in (1..edges.len()).rev() {
            let j = (rng.next_f32() * (i + 1) as f32) as usize;
            edges.swap(i, j.min(i));
        }

        let split_idx = (edges.len() as f32 * replace_ratio.clamp(0.0, 1.0)) as usize;
        let replaced_edges = edges[..split_idx].to_vec();
        let kept_edges = edges[split_idx..].to_vec();

        let mut explicit = self.clone();
        explicit.edges = kept_edges;

        let mut lpu = self.clone();
        lpu.edges = replaced_edges;

        (explicit, lpu)
    }
}
