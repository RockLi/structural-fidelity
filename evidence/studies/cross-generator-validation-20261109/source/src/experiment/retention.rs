//! Phase 3 Selective Explicit Retention Policy.
//!
//! Provides a manual, config-driven mechanism to designate which edge classes
//! remain **explicit** (routed per-event via `EventRouter`) vs. which are
//! **replaced** by the richer proxy aggregator.
//!
//! # Design Constraints
//! The retention policy is **manually specified**, not auto-learned:
//! - No automatic motif discovery.
//! - No dynamic rebalancing during simulation.
//! - Motif classes are enumerated via `MotifClass`; membership is set at config time.
//!
//! This lets us first answer *does selective retention help?* before attacking
//! the harder question of *how should we discover what to retain?*
//!
//! # Usage
//! ```rust,ignore
//! let policy = RetentionPolicy::new(vec![MotifClass::StrongInhibitoryLoop]);
//! let (kept, replaced) = policy.partition_edges(&full_circuit);
//! // `kept` → EventRouter (explicit)
//! // `replaced` → LpuTopologyIndex with 4-channel proxy
//! ```

use crate::connectivity::microcircuit::EIMicrocircuit;
use crate::connectivity::types::{PopulationType, SynapticEdge};
use crate::core::chunk::ChunkId;

/// Biological / structural edge classes for which manual retention may be configured.
///
/// Each variant must have a clear scientific justification for why those edges
/// cannot be reliably compressed by the richer proxy.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MotifClass {
    /// Strong inhibitory feedback loops (I→E with weight ≥ threshold).
    ///
    /// Justification: Phase 2 data show runaway/underdamping distortion correlates
    /// with the proxy being unable to model rapid I→E gain suppression.  Retaining
    /// these edges explicitly preserves the local braking mechanism.
    StrongInhibitoryLoop,

    /// Edges crossing a chunk boundary in a boundary-heavy topology.
    ///
    /// Justification: Phase 2 analysis shows boundary edges are the primary site
    /// of spectral and synchrony distortion in boundary-heavy benchmarks.
    BoundaryHeavyEdge,

    /// A general high-weight edge class regardless of E/I polarity.
    ///
    /// Useful when analysing which absolute weight threshold matters most.
    /// The minimum weight is stored as raw `u32` bit-pattern to allow `Eq` derivation
    /// (NaN inputs will panic at construction time via `HighWeightEdge::new`).
    HighWeightEdge {
        /// Edges with weight ≥ this value are retained explicitly.
        /// Use `HighWeightEdge::new(w)` to construct; stored as `f32::to_bits()`.
        min_weight_bits: u32,
    },

    /// Fast inhibitory-to-inhibitory feedback loops (I→I edges).
    ///
    /// Justification: I→I connections modulate inhibitory population activity.
    /// When proxy-compressed, the I→I suppression timing is smeared, leading
    /// to synchrony distortion and regime boundary shifts.  Retaining I→I
    /// edges explicitly preserves rapid oscillatory suppression of the
    /// inhibitory population. Requires `RetentionPolicy::with_inh_chunks`.
    FastInhibitoryLoop {
        /// Minimum I→I edge weight for retention. Stored as `f32::to_bits()`.
        min_weight_bits: u32,
    },

    /// Short E→I cycle edges: the excitatory arm of a reciprocal E↔I pair.
    ///
    /// Justification: When the I→E half of an E↔I cycle is retained explicitly
    /// (via `StrongInhibitoryLoop`) but the E→I half is proxied, the coupling
    /// asymmetry distorts cycle frequency and burst shape.  Retaining both
    /// halves of the short cycle reduces spectral distortion. Requires
    /// `RetentionPolicy::with_inh_chunks`.
    ShortCycleMotif {
        /// Minimum E→I edge weight for retention. Stored as `f32::to_bits()`.
        min_weight_bits: u32,
    },
}

impl MotifClass {
    /// Convenience constructor for `HighWeightEdge`. Panics if `min_weight` is NaN.
    pub fn high_weight(min_weight: f32) -> Self {
        assert!(!min_weight.is_nan(), "HighWeightEdge: min_weight must not be NaN");
        Self::HighWeightEdge { min_weight_bits: min_weight.to_bits() }
    }

    /// Convenience constructor for `FastInhibitoryLoop`. Panics if NaN.
    pub fn fast_inh_loop(min_weight: f32) -> Self {
        assert!(!min_weight.is_nan(), "FastInhibitoryLoop: min_weight must not be NaN");
        Self::FastInhibitoryLoop { min_weight_bits: min_weight.to_bits() }
    }

    /// Convenience constructor for `ShortCycleMotif`. Panics if NaN.
    pub fn short_cycle(min_weight: f32) -> Self {
        assert!(!min_weight.is_nan(), "ShortCycleMotif: min_weight must not be NaN");
        Self::ShortCycleMotif { min_weight_bits: min_weight.to_bits() }
    }
}

/// Manual retention policy: assigns each edge to either the explicit or proxy path.
#[derive(Debug, Clone)]
pub struct RetentionPolicy {
    /// Ordered list of motif classes to retain explicitly.
    /// Evaluated in order; the *first matching class* wins.
    retain_classes: Vec<MotifClass>,
    /// Weight threshold used by `MotifClass::StrongInhibitoryLoop`.
    pub strong_inh_weight_threshold: f32,
    /// Raw chunk IDs of inhibitory population chunks.
    /// Required for `FastInhibitoryLoop` and `ShortCycleMotif` classification
    /// (distinguishes I→I from I→E and E→I from E→E by target chunk membership).
    inh_chunk_ids: std::collections::HashSet<u32>,
}

impl RetentionPolicy {
    /// Create a retention policy that keeps the given motif classes explicit.
    ///
    /// `strong_inh_weight_threshold` controls the weight cutoff for
    /// `StrongInhibitoryLoop` classification.  A good starting value for
    /// balanced E/I networks is `0.5 * mean_inh_weight`.
    pub fn new(retain_classes: Vec<MotifClass>, strong_inh_weight_threshold: f32) -> Self {
        Self {
            retain_classes,
            strong_inh_weight_threshold,
            inh_chunk_ids: std::collections::HashSet::new(),
        }
    }

    /// Register inhibitory chunk IDs for `FastInhibitoryLoop` and `ShortCycleMotif`.
    ///
    /// Must be called before `partition_edges` when using either of those variants.
    /// Consecutive calls replace the previous set.
    pub fn with_inh_chunks(mut self, inh_ids: impl IntoIterator<Item = ChunkId>) -> Self {
        self.inh_chunk_ids = inh_ids.into_iter().map(|c| c.0).collect();
        self
    }

    /// Returns `true` if the given edge should be retained in the explicit path.
    fn should_retain(&self, edge: &SynapticEdge) -> bool {
        for class in &self.retain_classes {
            match class {
                MotifClass::StrongInhibitoryLoop => {
                    if edge.source_type == PopulationType::Inhibitory
                        && edge.weight >= self.strong_inh_weight_threshold
                    {
                        return true;
                    }
                }
                MotifClass::BoundaryHeavyEdge => {
                    // An edge crosses a chunk boundary iff source and target chunks differ.
                    if edge.source_chunk != edge.target_chunk {
                        return true;
                    }
                }
                MotifClass::HighWeightEdge { min_weight_bits } => {
                    if edge.weight >= f32::from_bits(*min_weight_bits) {
                        return true;
                    }
                }
                MotifClass::FastInhibitoryLoop { min_weight_bits } => {
                    // I→I: source inhibitory, target in inhibitory chunk set.
                    if edge.source_type == PopulationType::Inhibitory
                        && self.inh_chunk_ids.contains(&edge.target_chunk.0)
                        && edge.weight >= f32::from_bits(*min_weight_bits)
                    {
                        return true;
                    }
                }
                MotifClass::ShortCycleMotif { min_weight_bits } => {
                    // E→I: source excitatory, target in inhibitory chunk set.
                    if edge.source_type == PopulationType::Excitatory
                        && self.inh_chunk_ids.contains(&edge.target_chunk.0)
                        && edge.weight >= f32::from_bits(*min_weight_bits)
                    {
                        return true;
                    }
                }
            }
        }
        false
    }

    /// Partition `circuit` edges into two disjoint sets:
    /// - `(kept, replaced)` where `kept` stays explicit and `replaced` uses the proxy.
    ///
    /// Returns `(kept_edges, replaced_edges)`.
    /// The caller should build an `EventRouter` from `kept_edges` and an
    /// `LpuTopologyIndex` from the `replaced_edges` circuit.
    pub fn partition_edges(
        &self,
        circuit: &EIMicrocircuit,
    ) -> (Vec<SynapticEdge>, Vec<SynapticEdge>) {
        let mut kept = Vec::new();
        let mut replaced = Vec::new();

        for edge in circuit.all_edges() {
            if self.should_retain(edge) {
                kept.push(edge.clone());
            } else {
                replaced.push(edge.clone());
            }
        }
        (kept, replaced)
    }

    /// Summary statistics for the partition (useful for logging and the frontier report).
    pub fn partition_stats(&self, circuit: &EIMicrocircuit) -> RetentionStats {
        let (kept, replaced) = self.partition_edges(circuit);
        let total = kept.len() + replaced.len();
        RetentionStats {
            total_edges: total,
            kept_explicit: kept.len(),
            replaced_proxy: replaced.len(),
            retention_fraction: if total > 0 {
                kept.len() as f32 / total as f32
            } else {
                0.0
            },
        }
    }
}

/// Summary of a retention partition for logging and benchmark reports.
#[derive(Debug, Clone)]
pub struct RetentionStats {
    pub total_edges: usize,
    pub kept_explicit: usize,
    pub replaced_proxy: usize,
    /// Fraction of edges kept explicit (0.0 = all proxy, 1.0 = all explicit).
    pub retention_fraction: f32,
}

impl std::fmt::Display for RetentionStats {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "RetentionStats: total={} kept_explicit={} replaced_proxy={} fraction={:.3}",
            self.total_edges,
            self.kept_explicit,
            self.replaced_proxy,
            self.retention_fraction
        )
    }
}


#[cfg(test)]
mod tests {
    use super::*;
    use crate::connectivity::microcircuit::EIMicrocircuitSpec;
    use crate::connectivity::types::{PopulationType, SynapticEdge};
    use crate::core::chunk::ChunkId;

    /// Build a minimal 3-edge test circuit using the standard builder path.
    ///
    /// We build a tiny spec (3 E-chunks, 1 I-chunk) and then manually inject
    /// the three canonical test edges so the circuit contents are fully controlled.
    fn make_test_circuit() -> crate::connectivity::microcircuit::EIMicrocircuit {
        // Use a spec with p=0 everywhere so the builder produces zero edges,
        // then we'll wrap the edges we want in LocalProjections manually.
        let spec = EIMicrocircuitSpec {
            exc_chunks: vec![ChunkId(0), ChunkId(1)],
            inh_chunks: vec![ChunkId(2)],
            p_ee: 0.0,
            p_ei: 0.0,
            p_ie: 0.0,
            p_ii: 0.0,
            w_ee: 0.8,
            w_ei: 0.8,
            w_ie: 1.2,
            w_ii: 0.6,
            delay_slots: 1,
            rng_seed: 42,
            forbid_within_chunk: false,
            weight_spread: 0.0,
        };
        let mut circuit = spec.build(); // zero edges

        // Inject the three test edges manually.
        // E→E edge, weight 0.2
        circuit.ee.edges.push(SynapticEdge::new(
            ChunkId(0),
            ChunkId(1),
            PopulationType::Excitatory,
            0.2,
            1,
        ));
        // I→E edge (strong), weight 0.8  ← StrongInhibitoryLoop should retain this
        circuit.ie.edges.push(SynapticEdge::new(
            ChunkId(2),
            ChunkId(0),
            PopulationType::Inhibitory,
            0.8,
            1,
        ));
        // I→E edge (weak), weight 0.1
        circuit.ie.edges.push(SynapticEdge::new(
            ChunkId(2),
            ChunkId(1),
            PopulationType::Inhibitory,
            0.1,
            1,
        ));
        circuit
    }

    #[test]
    fn test_strong_inh_loop_retention() {
        let policy = RetentionPolicy::new(vec![MotifClass::StrongInhibitoryLoop], 0.5);
        let circuit = make_test_circuit();
        let (kept, replaced) = policy.partition_edges(&circuit);

        // Only the I→E edge with weight 0.8 should be kept.
        assert_eq!(kept.len(), 1, "expected 1 kept edge");
        assert_eq!(kept[0].weight, 0.8);
        // The other two edges should be replaced.
        assert_eq!(replaced.len(), 2, "expected 2 replaced edges");
    }

    #[test]
    fn test_empty_policy_replaces_all() {
        let policy = RetentionPolicy::new(vec![], 0.5);
        let circuit = make_test_circuit();
        let (kept, replaced) = policy.partition_edges(&circuit);
        assert_eq!(kept.len(), 0);
        assert_eq!(replaced.len(), 3);
    }

    #[test]
    fn test_retention_stats_fraction() {
        let policy = RetentionPolicy::new(vec![MotifClass::StrongInhibitoryLoop], 0.5);
        let circuit = make_test_circuit();
        let stats = policy.partition_stats(&circuit);
        assert_eq!(stats.total_edges, 3);
        assert_eq!(stats.kept_explicit, 1);
        assert!(
            (stats.retention_fraction - 1.0 / 3.0).abs() < 1e-5,
            "retention fraction should be ~1/3, got {}",
            stats.retention_fraction
        );
    }
}
