/// Benchmark C: Zero-Connectivity Memory Floor
///
/// Stage 1.3 goal: verify that the `next-brain` runtime can allocate and
/// hold large-scale neural populations in memory without a connectivity graph,
/// across three scale targets: 1M / 10M / 100M units.
///
/// Benchmarks two axes independently:
///   1. **Allocation throughput**: How fast can N units be allocated?
///   2. **Scheduler tick overhead**: When all chunks are dormant, what is the
///      per-step cost of the scheduler's pass over the chunk population?
///
/// Build with `RUSTFLAGS="-C target-cpu=native"` for consistent comparison
/// with Benchmarks A and B.
use criterion::{BenchmarkId, Criterion, Throughput, black_box, criterion_group, criterion_main};
use next_brain::{
    core::scheduler::Scheduler,
    layout::allocator::{MemoryFloorReport, SyntheticChunkAllocator},
};

// Scale targets (units). 100M requires ~2.8 GB RAM; run only if available.
const SCALES: &[usize] = &[1_000_000, 10_000_000, 100_000_000];
const UNITS_PER_CHUNK: usize = 1_000;

// ── C1: Allocation Throughput ──────────────────────────────────────────────
// Measures the wall-clock cost of calling `SyntheticChunkAllocator::build()`
// at each scale. This isolates heap allocation from compute.
fn bench_allocation_throughput(c: &mut Criterion) {
    let mut group = c.benchmark_group("MemoryFloor_Allocation");

    for &total_units in SCALES {
        // Skip 100M in CI-like environments with tight time budget.
        // Criterion will warn if it can't collect 100 samples in 5s.
        group.throughput(Throughput::Elements(total_units as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(total_units),
            &total_units,
            |b, &n| {
                let alloc = SyntheticChunkAllocator::new(n, UNITS_PER_CHUNK, 10.0);
                b.iter(|| {
                    let chunks = alloc.build();
                    black_box(chunks.len()); // prevent dead-code elimination
                });
            },
        );
    }
    group.finish();
}

// ── C2: Dormant Scheduler Tick Overhead ────────────────────────────────────
// Measures the per-step overhead of the Scheduler when ALL chunks are
// dormant (no active units, no pending events). This is the quiescent floor:
// the minimum scheduler cost at scale.
//
// Expected: should scale roughly linearly with chunk count as the scheduler
// must iterate over all chunks to confirm they have no due events.
fn bench_dormant_scheduler_tick(c: &mut Criterion) {
    let mut group = c.benchmark_group("MemoryFloor_DormantTick");

    // At 100M units that's 100,000 chunks — scheduler iteration dominates.
    for &total_units in SCALES {
        let num_chunks = total_units / UNITS_PER_CHUNK;
        group.throughput(Throughput::Elements(num_chunks as u64));
        group.bench_with_input(
            BenchmarkId::from_parameter(total_units),
            &total_units,
            |b, &n| {
                // Setup: build scheduler with all-dormant chunks.
                let alloc = SyntheticChunkAllocator::new(n, UNITS_PER_CHUNK, 10.0);
                let chunks = alloc.build();
                let mut scheduler = Scheduler::new(0.001);
                for chunk in chunks {
                    scheduler.add_chunk(chunk);
                }

                b.iter(|| {
                    black_box(scheduler.step());
                });
            },
        );
    }
    group.finish();
}

// ── C3: Memory Floor Report (one-shot print during benchmark run) ──────────
// Criterion calls each benchmark function once before sampling.
// We use a dedicated one-shot bench group (sample_size = 1) so the report
// prints exactly once without polluting timing results.
fn bench_memory_report(c: &mut Criterion) {
    let mut group = c.benchmark_group("MemoryFloor_Report");
    group.sample_size(10);

    group.bench_function("print_report", |b| {
        b.iter(|| {
            for &total_units in SCALES {
                let alloc = SyntheticChunkAllocator::new(total_units, UNITS_PER_CHUNK, 10.0);
                let report = MemoryFloorReport::generate(&alloc);
                black_box(report.summary());
            }
        })
    });
    group.finish();
}

criterion_group!(
    benches,
    bench_allocation_throughput,
    bench_dormant_scheduler_tick,
    bench_memory_report
);
criterion_main!(benches);
