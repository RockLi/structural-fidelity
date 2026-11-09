//! Minimal E/I recurrent microcircuit builder.
//!
//! Constructs the **nontrivial explicit connectivity baseline** required by Paper 2:
//! a balanced excitatory-inhibitory local microcircuit with four projection arms:
//!
//! ```text
//!  E ─┬─ E→E (recurrent excitation)
//!     └─ E→I (excitatory drive to inhibitory pool)
//!  I ─┬─ I→E (feedback inhibition)
//!     └─ I→I (inhibitory self-coupling)
//! ```
//!
//! # Design Principles
//! - **Static**: no plasticity, no rewiring.
//! - **Controlled**: all weights and delays are explicit and reproducible.
//! - **Nontrivial**: the E/I balance parameters are chosen to support
//!   self-sustained recurrent dynamics (not a trivially quiescent network).
//! - **Chunk-compatible**: edges map to ChunkId pairs used by `EventRouter`.

use crate::connectivity::types::{LocalProjection, PopulationType, SynapticEdge};
use crate::core::chunk::ChunkId;

/// Specification for a minimal E/I recurrent microcircuit.
///
/// Both the excitatory (`exc_chunks`) and inhibitory (`inh_chunks`) populations
/// are specified as contiguous ranges of chunk IDs.
#[derive(Debug, Clone)]
pub struct EIMicrocircuitSpec {
    /// Chunk IDs belonging to the excitatory population.
    pub exc_chunks: Vec<ChunkId>,
    /// Chunk IDs belonging to the inhibitory population.
    pub inh_chunks: Vec<ChunkId>,

    // ── Connection probabilities (0.0–1.0) ────────────────────────────────
    /// E→E connection probability.
    pub p_ee: f32,
    /// E→I connection probability.
    pub p_ei: f32,
    /// I→E connection probability.
    pub p_ie: f32,
    /// I→I connection probability.
    pub p_ii: f32,

    // ── Weights ───────────────────────────────────────────────────────────
    /// E→E synaptic weight (excitatory drive).
    pub w_ee: f32,
    /// E→I synaptic weight (excitatory drive to inhibitory pool).
    pub w_ei: f32,
    /// I→E synaptic weight (inhibitory feedback, typically negative or mapped to inh channel).
    pub w_ie: f32,
    /// I→I synaptic weight.
    pub w_ii: f32,

    // ── Delays (slots) ────────────────────────────────────────────────────
    /// Propagation delay for all local edges (slots).
    pub delay_slots: u64,

    // ── RNG seed for edge sampling ────────────────────────────────────────
    pub rng_seed: u64,

    // ── Constraints ───────────────────────────────────────────────────────
    /// If true, edges are only formed if source_chunk != target_chunk.
    /// Used for boundary-heavy benchmark topologies.
    pub forbid_within_chunk: bool,

    // ── Weight heterogeneity ───────────────────────────────────────────────
    /// Per-edge weight spread fraction (0.0 = homogeneous, i.e. all edges use
    /// the exact spec weight).  When > 0, each edge weight is sampled from
    /// `[w × (1 − spread), w × (1 + spread)]` using the same LCG RNG as the
    /// connectivity sampler, consuming one additional call per edge.
    ///
    /// Set to 0.0 in the homogeneous constructors to preserve the reference topology.
    pub weight_spread: f32,
}

impl EIMicrocircuitSpec {
    /// Create a spec with biologically plausible E/I defaults.
    ///
    /// Parameters chosen to produce self-sustained recurrent dynamics at ~10 Hz:
    /// - 80% excitatory, 20% inhibitory (cortical ratio)
    /// - Sparse local connectivity (p ≈ 0.1–0.2)
    /// - Balanced E/I weights (slightly net-excitatory to sustain activity)
    /// - 1-slot minimal delay (dt = 1 ms → 1 ms local propagation)
    pub fn balanced(exc_chunks: Vec<ChunkId>, inh_chunks: Vec<ChunkId>) -> Self {
        Self {
            exc_chunks,
            inh_chunks,
            p_ee: 0.10,
            p_ei: 0.20,
            p_ie: 0.20,
            p_ii: 0.15,
            w_ee: 0.8,
            w_ei: 0.8,
            w_ie: 1.2,
            w_ii: 0.6,
            delay_slots: 1,
            rng_seed: 42,
            forbid_within_chunk: false,
            weight_spread: 0.0,
        }
    }

    /// Boundary-heavy topology with **heterogeneous** per-edge weights.
    ///
    /// Identical connectivity structure to the E3 boundary-heavy benchmark (`forbid_within_chunk`,
    /// same p and mean-w values) but each edge weight is independently sampled from
    /// `[w × 0.5, w × 1.5]`.  With `StrongInhibitoryLoop` threshold = `w_ie` (1.4),
    /// roughly half the I→E edges fall above threshold, yielding ~11–13% retention
    /// (target: below the 15% retention budget).
    ///
    /// The homogeneous boundary-heavy spec (`rng_seed: 99`, `weight_spread: 0.0`)
    /// is **unchanged** and remains the reference comparator.
    pub fn boundary_heavy_hetero(exc_chunks: Vec<ChunkId>, inh_chunks: Vec<ChunkId>) -> Self {
        Self {
            exc_chunks,
            inh_chunks,
            p_ee: 0.15,
            p_ei: 0.25,
            p_ie: 0.25,
            p_ii: 0.20,
            w_ee: 0.6,
            w_ei: 0.8,
            w_ie: 1.4,
            w_ii: 0.5,
            delay_slots: 1,
            rng_seed: 200,   // distinct from the homogeneous seed (99) — separate population
            forbid_within_chunk: true,
            weight_spread: 0.50, // ±50%: w_ie ∈ [0.7, 2.1]; threshold=1.4 retains ~50% → ~12%
        }
    }

    /// Build all four projection arms as explicit edges.
    ///
    /// When `weight_spread > 0`, each edge weight is independently sampled via
    /// `sample_weight()` after the connectivity coin-flip, consuming one additional
    /// LCG call per accepted edge.
    ///
    /// Uses a deterministic LCG sampler seeded by `rng_seed` for reproducible
    /// connectivity sampling without pulling in the `rand` crate.
    pub fn build(&self) -> EIMicrocircuit {
        let mut ee = LocalProjection {
            label: "E→E".to_string(),
            source_type: PopulationType::Excitatory,
            edges: Vec::new(),
        };
        let mut ei = LocalProjection {
            label: "E→I".to_string(),
            source_type: PopulationType::Excitatory,
            edges: Vec::new(),
        };
        let mut ie = LocalProjection {
            label: "I→E".to_string(),
            source_type: PopulationType::Inhibitory,
            edges: Vec::new(),
        };
        let mut ii = LocalProjection {
            label: "I→I".to_string(),
            source_type: PopulationType::Inhibitory,
            edges: Vec::new(),
        };

        let mut rng = LcgRng::new(self.rng_seed);
        let allow = |src: ChunkId, tgt: ChunkId| !(self.forbid_within_chunk && src == tgt);
        let spread = self.weight_spread;

        // E→E: each excitatory chunk may project to each other excitatory chunk.
        for &src in &self.exc_chunks {
            for &tgt in &self.exc_chunks {
                if src != tgt && allow(src, tgt) && rng.next_f32() < self.p_ee {
                    let w = sample_weight(&mut rng, self.w_ee, spread);
                    ee.edges.push(SynapticEdge::new(
                        src,
                        tgt,
                        PopulationType::Excitatory,
                        w,
                        self.delay_slots,
                    ));
                }
            }
        }

        // E→I: excitatory chunks project to inhibitory chunks.
        for &src in &self.exc_chunks {
            for &tgt in &self.inh_chunks {
                if allow(src, tgt) && rng.next_f32() < self.p_ei {
                    let w = sample_weight(&mut rng, self.w_ei, spread);
                    ei.edges.push(SynapticEdge::new(
                        src,
                        tgt,
                        PopulationType::Excitatory,
                        w,
                        self.delay_slots,
                    ));
                }
            }
        }

        // I→E: inhibitory chunks project back to excitatory chunks.
        for &src in &self.inh_chunks {
            for &tgt in &self.exc_chunks {
                if allow(src, tgt) && rng.next_f32() < self.p_ie {
                    let w = sample_weight(&mut rng, self.w_ie, spread);
                    ie.edges.push(SynapticEdge::new(
                        src,
                        tgt,
                        PopulationType::Inhibitory,
                        w,
                        self.delay_slots,
                    ));
                }
            }
        }

        // I→I: inhibitory self-coupling.
        for &src in &self.inh_chunks {
            for &tgt in &self.inh_chunks {
                if src != tgt && allow(src, tgt) && rng.next_f32() < self.p_ii {
                    let w = sample_weight(&mut rng, self.w_ii, spread);
                    ii.edges.push(SynapticEdge::new(
                        src,
                        tgt,
                        PopulationType::Inhibitory,
                        w,
                        self.delay_slots,
                    ));
                }
            }
        }

        EIMicrocircuit { ee, ei, ie, ii }
    }
}

/// A fully materialized E/I microcircuit with four explicit projection arms.
/// Sample a per-edge weight: uniform in `[base*(1−spread), base*(1+spread)]` when
/// `spread > 0`, otherwise returns `base` exactly (homogeneous case).
fn sample_weight(rng: &mut LcgRng, base: f32, spread: f32) -> f32 {
    if spread > 0.0 {
        base * rng.next_f32_range(1.0 - spread, 1.0 + spread)
    } else {
        base
    }
}

#[derive(Debug)]
pub struct EIMicrocircuit {
    pub ee: LocalProjection,
    pub ei: LocalProjection,
    pub ie: LocalProjection,
    pub ii: LocalProjection,
}

impl EIMicrocircuit {
    /// Total number of explicit edges across all projection arms.
    pub fn total_edge_count(&self) -> usize {
        self.ee.edge_count() + self.ei.edge_count() + self.ie.edge_count() + self.ii.edge_count()
    }

    /// Total memory used by all explicit edges (bytes).
    pub fn total_memory_bytes(&self) -> usize {
        self.ee.memory_bytes()
            + self.ei.memory_bytes()
            + self.ie.memory_bytes()
            + self.ii.memory_bytes()
    }

    /// Return a human-readable summary of edge counts across all arms.
    pub fn summary(&self) -> String {
        format!(
            "EIMicrocircuit: E→E={}, E→I={}, I→E={}, I→I={} | total={} edges | {:.1} KB",
            self.ee.edge_count(),
            self.ei.edge_count(),
            self.ie.edge_count(),
            self.ii.edge_count(),
            self.total_edge_count(),
            self.total_memory_bytes() as f64 / 1024.0,
        )
    }

    /// Iterator over all edges across all arms.
    pub fn all_edges(&self) -> impl Iterator<Item = &SynapticEdge> {
        self.ee
            .edges
            .iter()
            .chain(self.ei.edges.iter())
            .chain(self.ie.edges.iter())
            .chain(self.ii.edges.iter())
    }

    /// Split this microcircuit into two: an explicitly preserved circuit and a proxy-replaced circuit.
    pub fn split_by_ratio(&self, ratio: f32, seed: u64) -> (EIMicrocircuit, EIMicrocircuit) {
        let (ee_kept, ee_repl) = self.ee.split(ratio, seed);
        let (ei_kept, ei_repl) = self.ei.split(ratio, seed + 1);
        let (ie_kept, ie_repl) = self.ie.split(ratio, seed + 2);
        let (ii_kept, ii_repl) = self.ii.split(ratio, seed + 3);

        (
            EIMicrocircuit {
                ee: ee_kept,
                ei: ei_kept,
                ie: ie_kept,
                ii: ii_kept,
            },
            EIMicrocircuit {
                ee: ee_repl,
                ei: ei_repl,
                ie: ie_repl,
                ii: ii_repl,
            },
        )
    }

    /// Helper to grab references to all arms, useful for EventRouter construction.
    pub fn all_proj_refs(&self) -> [&LocalProjection; 4] {
        [&self.ee, &self.ei, &self.ie, &self.ii]
    }
}

// ── Minimal LCG RNG (no rand dependency) ──────────────────────────────────

/// A minimal Linear Congruential Generator for reproducible connectivity
/// sampling without external crate dependencies.
pub(crate) struct LcgRng {
    state: u64,
}

impl LcgRng {
    pub(crate) fn new(seed: u64) -> Self {
        Self {
            state: seed.wrapping_add(1),
        }
    }

    /// Advance and return a value in `[lo, hi)`.
    pub(crate) fn next_f32_range(&mut self, lo: f32, hi: f32) -> f32 {
        lo + self.next_f32() * (hi - lo)
    }

    /// Advance and return next value in [0.0, 1.0).
    pub(crate) fn next_f32(&mut self) -> f32 {
        self.state = self
            .state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        // Use upper 24 bits for f32 mantissa.
        ((self.state >> 40) as f32) / ((1u64 << 24) as f32)
    }
}
