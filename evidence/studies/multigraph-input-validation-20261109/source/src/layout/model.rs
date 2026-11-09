//! Stage 1.4.1: Model Description Structs
//!
//! User-facing declarative types for specifying neural network topology.
//! These structs sit above the chunk/scheduler layer and define the "what",
//! not the "how" — the compiler layer translates them into a `CompiledLayout`.
//!
//! # Design Principles
//! - **Declarative over imperative**: users describe populations and connectivity
//!   at a logical level; the compiler decides chunk assignments and memory layout.
//! - **No Phase-2 premature binding**: no learning rules, no morphology, no rewiring.
//! - **LPU-compatible**: the locality model maps cleanly to chunk boundaries later.

/// Unique identifier for a region (cortical area, nucleus, layer, etc.).
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct RegionId(pub String);

impl RegionId {
    pub fn new(name: impl Into<String>) -> Self {
        Self(name.into())
    }
}

impl std::fmt::Display for RegionId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

/// Neuron type for future kernel dispatch.
///
/// Phase 1: only `LeakyIntegrateFire` is simulated.
/// Phase 2 onwards: `Izhikevich`, `AdEx`, and custom LPU kernels will be added.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NeuronType {
    /// Simplified leaky integrate-and-fire (current Phase 1 kernel).
    LeakyIntegrateFire,
    // Future: Izhikevich, AdaptiveExponential, ...
}

impl Default for NeuronType {
    fn default() -> Self {
        Self::LeakyIntegrateFire
    }
}

/// Specification for a single population of neurons within a region.
///
/// A population is a logical grouping of `num_units` neurons of the same type.
/// The compiler assigns them to one or more chunks based on `units_per_chunk`.
#[derive(Debug, Clone)]
pub struct PopulationSpec {
    /// Human-readable label for this population (e.g., "V1_L4_exc").
    pub label: String,
    /// Parent region this population belongs to.
    pub region_id: RegionId,
    /// Total number of units in this population.
    pub num_units: usize,
    /// Neuron dynamics type (determines which kernel is used at step time).
    pub neuron_type: NeuronType,
    /// Optional: override units per chunk (defaults to `NetworkBuilder::default_units_per_chunk`).
    pub units_per_chunk_override: Option<usize>,
}

impl PopulationSpec {
    /// Create a new population spec with default neuron type (LIF).
    pub fn new(label: impl Into<String>, region_id: RegionId, num_units: usize) -> Self {
        Self {
            label: label.into(),
            region_id,
            num_units,
            neuron_type: NeuronType::default(),
            units_per_chunk_override: None,
        }
    }

    /// Override units-per-chunk for this population.
    ///
    /// > **⚠ Benchmark comparability warning**
    /// > Phase 1 architecture mandates a *fixed* global chunk size for all
    /// > populations so that Benchmark A/B/C results are directly comparable.
    /// > Using a per-population override produces a heterogeneous layout that
    /// > weakens the validity of cross-benchmark conclusions.
    /// > Reserve this method for Phase 2+ experiments.
    pub fn with_chunk_size(mut self, size: usize) -> Self {
        self.units_per_chunk_override = Some(size);
        self
    }

    /// Override neuron type.
    pub fn with_neuron_type(mut self, nt: NeuronType) -> Self {
        self.neuron_type = nt;
        self
    }
}

/// Specification for a region: a named collection of populations.
///
/// Regions correspond to macro-anatomical areas (e.g., "V1", "prefrontal cortex").
/// In Phase 1 they are purely logical containers — no spatial embedding.
#[derive(Debug, Clone)]
pub struct RegionSpec {
    pub id: RegionId,
    /// Human-readable description (for reports/docs).
    pub description: String,
    /// Populations within this region.
    pub populations: Vec<PopulationSpec>,
}

impl RegionSpec {
    pub fn new(id: impl Into<String>, description: impl Into<String>) -> Self {
        Self {
            id: RegionId::new(id),
            description: description.into(),
            populations: Vec::new(),
        }
    }

    /// Add a population to this region.
    pub fn add_population(mut self, pop: PopulationSpec) -> Self {
        self.populations.push(pop);
        self
    }

    /// Total units across all populations in this region.
    pub fn total_units(&self) -> usize {
        self.populations.iter().map(|p| p.num_units).sum()
    }
}
