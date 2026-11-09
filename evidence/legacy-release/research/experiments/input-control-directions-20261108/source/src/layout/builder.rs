//! Stage 1.4.2: NetworkBuilder and CompiledLayout
//!
//! Translates a declarative model description (RegionSpec / PopulationSpec)
//! into a concrete runtime layout: a flat list of chunks ready to be loaded
//! into a Scheduler.
//!
//! # Compilation pipeline
//! ```no_run
//! // Logic:
//! // Vec<RegionSpec>
//! //     └─ NetworkBuilder::compile()
//! //         └─ CompiledLayout  (owns the Vec<Chunk>)
//! //             └─ Simulation::from_layout()
//! //                 └─ Scheduler (drives the simulation loop)
//! ```

use crate::core::chunk::{Chunk, ChunkId, ChunkStatus, GridCoord};
use crate::layout::model::{PopulationSpec, RegionId, RegionSpec};

/// Compilation error types.
#[derive(Debug)]
pub enum BuildError {
    /// A population has zero units.
    EmptyPopulation { label: String },
    /// units_per_chunk is zero.
    InvalidChunkSize,
    /// No regions / populations were provided.
    EmptyModel,
    /// Two populations share the same label; `find_population` would be ambiguous.
    DuplicatePopulationLabel { label: String },
    /// A population overrides the global chunk size while strict mode is enabled.
    ///
    /// Phase 1 architecture mandates a fixed chunk resolution for benchmark
    /// comparability. Enable strict mode via `NetworkBuilder::enforce_uniform_chunk_size()`.
    HeterogeneousChunkSize {
        label: String,
        override_size: usize,
        default_size: usize,
    },
}

impl std::fmt::Display for BuildError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptyPopulation { label } => write!(f, "Population '{}' has 0 units", label),
            Self::InvalidChunkSize => write!(f, "units_per_chunk must be > 0"),
            Self::EmptyModel => write!(f, "Model contains no populations"),
            Self::DuplicatePopulationLabel { label } => write!(
                f,
                "Duplicate population label '{}'; labels must be unique",
                label
            ),
            Self::HeterogeneousChunkSize {
                label,
                override_size,
                default_size,
            } => write!(
                f,
                "Population '{}' uses chunk size {} which differs from the builder \
                     default {} (strict Phase 1 mode: all populations must use a uniform \
                     chunk size for benchmark comparability)",
                label, override_size, default_size
            ),
        }
    }
}

/// Chunk range assigned to a single population.
#[derive(Debug, Clone)]
pub struct PopulationChunkRange {
    pub region_id: RegionId,
    pub population_label: String,
    /// Inclusive start of the chunk ID range.
    pub chunk_id_start: u32,
    /// Exclusive end of the chunk ID range.
    pub chunk_id_end: u32,
    /// Units per chunk for full chunks in this population.
    pub units_per_chunk: usize,
    /// Actual total units in this population (authoritative; last chunk may be partial).
    pub num_units: usize,
}

impl PopulationChunkRange {
    /// Number of chunks assigned to this population.
    pub fn num_chunks(&self) -> usize {
        (self.chunk_id_end - self.chunk_id_start) as usize
    }

    /// True total units in this population.
    ///
    /// Uses the stored `num_units` value, which is authoritative even when
    /// the final chunk is only partially filled.
    pub fn total_units(&self) -> usize {
        self.num_units
    }
}

/// The compiled, runtime-ready representation of the network.
///
/// Holds the allocated `Vec<Chunk>` and the index mapping each population
/// to its chunk range. This is the result of `NetworkBuilder::compile()`.
#[derive(Debug)]
pub struct CompiledLayout {
    /// All allocated chunks, in chunk-ID order.
    pub chunks: Vec<Chunk>,
    /// Mapping from population label to chunk range.
    pub population_map: Vec<PopulationChunkRange>,
    /// Total unit count across the entire model.
    pub total_units: usize,
}

impl CompiledLayout {
    /// Look up the chunk range for a population by label.
    pub fn find_population(&self, label: &str) -> Option<&PopulationChunkRange> {
        self.population_map
            .iter()
            .find(|p| p.population_label == label)
    }

    /// Total memory used by all SoA state arrays (bytes).
    pub fn state_memory_bytes(&self) -> usize {
        self.chunks.iter().map(|c| c.state_memory_bytes()).sum()
    }

    /// Human-readable summary of the compiled layout.
    pub fn summary(&self) -> String {
        let mb = self.state_memory_bytes() as f64 / (1024.0 * 1024.0);
        format!(
            "CompiledLayout: {} regions, {} populations, {} chunks, {} units, {:.1} MB state",
            self.population_map
                .iter()
                .map(|p| &p.region_id)
                .collect::<std::collections::HashSet<_>>()
                .len(),
            self.population_map.len(),
            self.chunks.len(),
            self.total_units,
            mb,
        )
    }
}

/// Builder that compiles a declarative model spec into a `CompiledLayout`.
pub struct NetworkBuilder {
    /// Default units per chunk (can be overridden per population).
    pub default_units_per_chunk: usize,
    /// Field decay time constant (ms) for all chunk contexts.
    pub field_decay_tau: f32,
    /// If true, `compile()` rejects any population with a per-population chunk-size
    /// override that differs from `default_units_per_chunk`.
    ///
    /// Enable via `enforce_uniform_chunk_size()`. Default: `false` (permissive).
    strict_chunk_size: bool,
    /// Registered regions.
    regions: Vec<RegionSpec>,
}

impl NetworkBuilder {
    /// Create a new builder with Phase 1 defaults.
    ///
    /// **Strict chunk-size mode is enabled by default.** `compile()` will return
    /// `Err(BuildError::HeterogeneousChunkSize)` if any population uses a
    /// per-population chunk-size override that differs from `default_units_per_chunk`.
    ///
    /// This enforces the Phase 1 architecture requirement that all benchmark
    /// populations use a fixed, uniform chunk resolution (Benchmark A/B/C comparability).
    ///
    /// For Phase 2+ experiments that need heterogeneous chunk sizes, use
    /// [`NetworkBuilder::new_permissive()`] instead.
    ///
    /// - `units_per_chunk`: 1,000 — matches Benchmark A/B/C configuration.
    /// - `field_decay_tau`: 10.0 ms — biologically plausible cortical time constant.
    pub fn new() -> Self {
        Self {
            default_units_per_chunk: 1_000,
            field_decay_tau: 10.0,
            strict_chunk_size: true, // Phase 1 default: fixed grid enforced
            regions: Vec::new(),
        }
    }

    /// Create a builder in permissive mode, allowing per-population chunk-size overrides.
    ///
    /// Use this for Phase 2+ experiments where heterogeneous chunk sizes are intentional.
    /// For Phase 1 benchmark models, prefer [`NetworkBuilder::new()`] (strict by default).
    pub fn new_permissive() -> Self {
        Self {
            default_units_per_chunk: 1_000,
            field_decay_tau: 10.0,
            strict_chunk_size: false,
            regions: Vec::new(),
        }
    }

    /// Override the default chunk size.
    pub fn with_chunk_size(mut self, size: usize) -> Self {
        self.default_units_per_chunk = size;
        self
    }

    /// Override the field decay tau.
    pub fn with_field_decay_tau(mut self, tau: f32) -> Self {
        self.field_decay_tau = tau;
        self
    }

    /// Register a region spec.
    pub fn add_region(mut self, region: RegionSpec) -> Self {
        self.regions.push(region);
        self
    }

    /// Compile the model into a `CompiledLayout` ready for `Simulation`.
    pub fn compile(self) -> Result<CompiledLayout, BuildError> {
        // Collect all populations across all regions.
        let all_pops: Vec<(&RegionSpec, &PopulationSpec)> = self
            .regions
            .iter()
            .flat_map(|r| r.populations.iter().map(move |p| (r, p)))
            .collect();

        if all_pops.is_empty() {
            return Err(BuildError::EmptyModel);
        }

        // Validate label uniqueness before allocating anything.
        {
            use std::collections::HashSet;
            let mut seen = HashSet::new();
            for (_, pop) in &all_pops {
                if !seen.insert(pop.label.as_str()) {
                    return Err(BuildError::DuplicatePopulationLabel {
                        label: pop.label.clone(),
                    });
                }
            }
        }

        // Phase 1 benchmark-comparability guard:
        // Heterogeneous chunk sizes across populations weaken Benchmark A/B/C comparability.
        // In strict mode: hard error on any override that differs from the global default.
        // In permissive mode (default): debug-build advisory warning only.
        for (_, pop) in &all_pops {
            if let Some(override_size) = pop.units_per_chunk_override {
                if override_size != self.default_units_per_chunk {
                    if self.strict_chunk_size {
                        return Err(BuildError::HeterogeneousChunkSize {
                            label: pop.label.clone(),
                            override_size,
                            default_size: self.default_units_per_chunk,
                        });
                    } else {
                        #[cfg(debug_assertions)]
                        eprintln!(
                            "[next-brain::builder] WARNING: population '{}' uses chunk size {} \
                             which differs from the builder default {}. This weakens Phase 1 \
                             benchmark comparability. Use enforce_uniform_chunk_size() to make \
                             this a hard error, or reserve overrides for Phase 2+ experiments.",
                            pop.label, override_size, self.default_units_per_chunk
                        );
                    }
                }
            }
        }

        let mut chunks: Vec<Chunk> = Vec::new();
        let mut population_map: Vec<PopulationChunkRange> = Vec::new();
        let mut total_units = 0usize;
        let mut next_chunk_id: u32 = 0;

        for (region, pop) in &all_pops {
            if pop.num_units == 0 {
                return Err(BuildError::EmptyPopulation {
                    label: pop.label.clone(),
                });
            }

            let upc = pop
                .units_per_chunk_override
                .unwrap_or(self.default_units_per_chunk);

            if upc == 0 {
                return Err(BuildError::InvalidChunkSize);
            }

            // Ceiling division: last chunk may have fewer units.
            let num_full_chunks = pop.num_units / upc;
            let remainder = pop.num_units % upc;

            let chunk_start = next_chunk_id;

            // Full chunks.
            for i in 0..num_full_chunks {
                let id = ChunkId(next_chunk_id);
                let coord = GridCoord {
                    x: next_chunk_id as i32,
                    y: 0,
                    z: 0,
                };
                let mut chunk = Chunk::new(id, coord, upc, self.field_decay_tau);
                // Start dormant; external stimulus will wake them.
                chunk.status = ChunkStatus::Dormant;
                chunks.push(chunk);
                next_chunk_id += 1;
                let _ = i;
            }

            // Remainder chunk (partial fill).
            if remainder > 0 {
                let id = ChunkId(next_chunk_id);
                let coord = GridCoord {
                    x: next_chunk_id as i32,
                    y: 0,
                    z: 0,
                };
                let mut chunk = Chunk::new(id, coord, remainder, self.field_decay_tau);
                chunk.status = ChunkStatus::Dormant;
                chunks.push(chunk);
                next_chunk_id += 1;
            }

            let chunk_end = next_chunk_id;
            total_units += pop.num_units;

            population_map.push(PopulationChunkRange {
                region_id: region.id.clone(),
                population_label: pop.label.clone(),
                chunk_id_start: chunk_start,
                chunk_id_end: chunk_end,
                units_per_chunk: upc,
                num_units: pop.num_units,
            });
        }

        Ok(CompiledLayout {
            chunks,
            population_map,
            total_units,
        })
    }
}

impl Default for NetworkBuilder {
    fn default() -> Self {
        Self::new()
    }
}
