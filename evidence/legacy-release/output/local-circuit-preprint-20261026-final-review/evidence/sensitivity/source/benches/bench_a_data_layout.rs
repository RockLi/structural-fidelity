//! Benchmark A: Data Layout Comparison — AoS vs SoA vs Block-SoA
//!
//! # Goal
//! Validate that SoA chunk-local state outperforms a naïve AoS baseline for
//! bulk neural state updates at scale, and characterize where Block-SoA
//! (cache-line-aligned grouped layout) closes the gap or further improves
//! on standard SoA.
//!
//! # Arms
//! | Arm | Type | Key hypothesis |
//! |-----|------|----------------|
//! | `AoS_state_update` | [`AosStateBaseline`] | Control (naïve layout) |
//! | `SoA_state_update_branchy` | [`ChunkStateArrays::step_euler`] | Branch-heavy SoA |
//! | `SoA_state_update_simd` | [`ChunkStateArrays::step_euler_simd_friendly`] | Branchless SoA (AVX2) |
//! | `BlockSoA_state_update` | [`BlockSoaState::step_euler`] | Block-grouped, cache-local SoA |
//!
//! # Build
//! ```bash
//! RUSTFLAGS="-C target-cpu=native" cargo bench --bench bench_a_data_layout
//! ```
//! Without `target-cpu=native` the SIMD and Block-SoA arms will use scalar
//! fallbacks; the comparison will still be valid but AVX2 throughput won't show.

use criterion::{BenchmarkId, Criterion, Throughput, black_box, criterion_group, criterion_main};
use next_brain::state::{
    ChunkStateArrays, aos_baseline::AosStateBaseline, block_soa::BlockSoaState,
};

/// Unit counts swept in every arm. Covers the 10× scaling range to expose
/// cache-capacity effects (L1 → L2 → L3 → DRAM crossover).
const UNIT_COUNTS: &[usize] = &[100_000, 1_000_000, 10_000_000];
const DT: f32 = 0.001;

// ── Arm 1: AoS baseline ──────────────────────────────────────────────────────

fn bench_aos(c: &mut Criterion) {
    let mut group = c.benchmark_group("AoS_state_update");
    for &n in UNIT_COUNTS {
        group.throughput(Throughput::Elements(n as u64));
        group.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &n| {
            let mut state = AosStateBaseline::new(n);
            b.iter(|| {
                state.step_euler(black_box(DT), black_box(0));
            });
        });
    }
    group.finish();
}

// ── Arm 2: Standard SoA (branchy) ────────────────────────────────────────────

fn bench_soa(c: &mut Criterion) {
    let mut group = c.benchmark_group("SoA_state_update_branchy");
    for &n in UNIT_COUNTS {
        group.throughput(Throughput::Elements(n as u64));
        group.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &n| {
            let mut state = ChunkStateArrays::new(n);
            b.iter(|| {
                state.step_euler(black_box(DT), black_box(0));
            });
        });
    }
    group.finish();
}

// ── Arm 3: Standard SoA (SIMD-friendly / branchless) ─────────────────────────

fn bench_soa_simd(c: &mut Criterion) {
    let mut group = c.benchmark_group("SoA_state_update_simd");
    for &n in UNIT_COUNTS {
        group.throughput(Throughput::Elements(n as u64));
        group.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &n| {
            let mut state = ChunkStateArrays::new(n);
            b.iter(|| {
                state.step_euler_simd_friendly(black_box(DT), black_box(0));
            });
        });
    }
    group.finish();
}

// ── Arm 4: Block-SoA (8-unit blocks, cache-line-local) ───────────────────────

fn bench_block_soa(c: &mut Criterion) {
    let mut group = c.benchmark_group("BlockSoA_state_update");
    for &n in UNIT_COUNTS {
        group.throughput(Throughput::Elements(n as u64));
        group.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &n| {
            let mut state = BlockSoaState::new(n);
            b.iter(|| {
                state.step_euler(black_box(DT), black_box(0));
            });
        });
    }
    group.finish();
}

criterion_group!(
    benches,
    bench_aos,
    bench_soa,
    bench_soa_simd,
    bench_block_soa
);
criterion_main!(benches);
