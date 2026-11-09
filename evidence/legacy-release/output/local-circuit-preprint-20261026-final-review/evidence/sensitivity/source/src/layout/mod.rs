/// Layout modules: Model Description Layer, RegionSpec, PopulationSpec.
pub mod allocator;
pub mod builder;
pub mod model;
pub mod simulation;

// Re-export primary user-facing API surface for Stage 1.4.
pub use builder::{CompiledLayout, NetworkBuilder};
pub use model::{NeuronType, PopulationSpec, RegionId, RegionSpec};
pub use simulation::{Simulation, SimulationMetrics};
