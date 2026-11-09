//! Phase 2 Example Use Cases module.
//!
//! Demonstrates that the Phase 2 runtime is a minimally usable platform for
//! studying local neural dynamics questions, not only a benchmarking substrate.
//!
//! # Examples
//! - [`ei_stability`]: E/I stability sweep across inhibition-strength regimes.
//! - [`panic_motif`]: Panic-like runaway activation under inhibition perturbation.

pub mod ei_stability;
pub mod panic_motif;
