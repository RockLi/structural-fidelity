/// Benchmark B (Refined): SoA vs AoS Re-evaluation under System Workloads.
///
/// Goal: Determine if the Phase 1.1 AoS advantage holds under sparse execution,
/// delayed activation, and selective state access scenarios.
///
/// Build with `RUSTFLAGS="-C target-cpu=native"` to unlock AVX2 in the SoA kernel.
/// The SoA Chunk now uses `step_euler_simd_friendly` internally.
use criterion::{BenchmarkId, Criterion, Throughput, criterion_group, criterion_main};
use next_brain::core::chunk::{Chunk, ChunkId, DelayedEvent, GridCoord};
use next_brain::core::chunk_aos::ChunkAoS;
use next_brain::core::scheduler::Scheduler;
use next_brain::core::scheduler_aos::SchedulerAoS;

const NUM_CHUNKS: usize = 1000;
const UNITS_PER_CHUNK: usize = 1000; // 1M units total

/// Setup standard SoA scheduler for benchmarking.
fn setup_soa(active_ratio: f32) -> (Scheduler, Vec<ChunkId>) {
    let mut scheduler = Scheduler::new(0.001);
    let mut active_ids = Vec::new();
    for i in 0..NUM_CHUNKS {
        let id = ChunkId(i as u32);
        let mut chunk = Chunk::new(
            id,
            GridCoord {
                x: i as i32,
                y: 0,
                z: 0,
            },
            UNITS_PER_CHUNK,
            10.0,
        );
        let should_be_active = (i as f32 / NUM_CHUNKS as f32) < active_ratio;
        if should_be_active {
            active_ids.push(id);
        } else {
            for s in chunk.state.spike_flags.iter_mut() {
                *s = 0.0;
            }
            chunk.step(0.001, 0);
        }
        scheduler.add_chunk(chunk);
    }
    (scheduler, active_ids)
}

/// Setup standard AoS scheduler mirror for benchmarking.
fn setup_aos(active_ratio: f32) -> (SchedulerAoS, Vec<ChunkId>) {
    let mut scheduler = SchedulerAoS::new(0.001);
    let mut active_ids = Vec::new();
    for i in 0..NUM_CHUNKS {
        let id = ChunkId(i as u32);
        let mut chunk = ChunkAoS::new(
            id,
            GridCoord {
                x: i as i32,
                y: 0,
                z: 0,
            },
            UNITS_PER_CHUNK,
            10.0,
        );
        let should_be_active = (i as f32 / NUM_CHUNKS as f32) < active_ratio;
        if should_be_active {
            active_ids.push(id);
        } else {
            for n in chunk.state.units.iter_mut() {
                n.spike_flag = 0.0;
            }
            chunk.step(0.001, 0);
        }
        scheduler.add_chunk(chunk);
    }
    (scheduler, active_ids)
}

/// Comparison 1: Sparse Activation Sweep (100% down to 0.1%).
fn bench_sparsity_comparison(c: &mut Criterion) {
    let ratios = [0.001, 0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 1.0];
    let mut group = c.benchmark_group("Sparsity_Comparison_SoA_vs_AoS");
    group.throughput(Throughput::Elements((NUM_CHUNKS * UNITS_PER_CHUNK) as u64));

    for &r in &ratios {
        let parameter = format!("ratio_{}", r);

        // Benchmark SoA
        group.bench_with_input(BenchmarkId::new("SoA", &parameter), &r, |b, &ratio| {
            let (mut scheduler, active_ids) = setup_soa(ratio);
            b.iter(|| {
                let slot = scheduler.current_slot;
                for &id in &active_ids {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: id,
                        target_slot: slot,
                        signal_strength: 0.1,
                    });
                }
                scheduler.step();
            });
        });

        // Benchmark AoS
        group.bench_with_input(BenchmarkId::new("AoS", &parameter), &r, |b, &ratio| {
            let (mut scheduler, active_ids) = setup_aos(ratio);
            b.iter(|| {
                let slot = scheduler.current_slot;
                for &id in &active_ids {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: id,
                        target_slot: slot,
                        signal_strength: 0.1,
                    });
                }
                scheduler.step();
            });
        });
    }
    group.finish();
}

/// Comparison 1b: Crossover Scan — fine-grained sweep between 10% and 30%.
///
/// Goal: Precisely identify the regime boundary (the active-chunk ratio at which
/// SoA SIMD and AoS cross over in performance) for use in technical reports and papers.
fn bench_crossover_scan(c: &mut Criterion) {
    // Fine-grained: 5% steps between 5% and 30%.
    let ratios: &[f32] = &[0.05, 0.10, 0.15, 0.20, 0.25, 0.30];
    let mut group = c.benchmark_group("Crossover_Scan_SoA_vs_AoS");
    group.throughput(Throughput::Elements((NUM_CHUNKS * UNITS_PER_CHUNK) as u64));

    for &r in ratios {
        let parameter = format!("pct_{}", (r * 100.0) as u32);

        group.bench_with_input(BenchmarkId::new("SoA", &parameter), &r, |b, &ratio| {
            let (mut scheduler, active_ids) = setup_soa(ratio);
            b.iter(|| {
                let slot = scheduler.current_slot;
                for &id in &active_ids {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: id,
                        target_slot: slot,
                        signal_strength: 0.1,
                    });
                }
                scheduler.step();
            });
        });

        group.bench_with_input(BenchmarkId::new("AoS", &parameter), &r, |b, &ratio| {
            let (mut scheduler, active_ids) = setup_aos(ratio);
            b.iter(|| {
                let slot = scheduler.current_slot;
                for &id in &active_ids {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: id,
                        target_slot: slot,
                        signal_strength: 0.1,
                    });
                }
                scheduler.step();
            });
        });
    }
    group.finish();
}

/// Comparison 2: Selective State Access Workloads.
/// Workload A: "Spike Scan" - Only check spike_flags and update refractory status.
fn bench_selective_access(c: &mut Criterion) {
    let mut group = c.benchmark_group("Selective_Access_Workload_SpikeScan");
    let n = 1_000_000;
    group.throughput(Throughput::Elements(n as u64));

    // SoA Spike Scan Only
    group.bench_function("SoA_SpikeScan_Only", |b| {
        let mut state = next_brain::state::ChunkStateArrays::new(n);
        b.iter(|| {
            state.step_spikes_only(0);
        });
    });

    // AoS "Selective" equivalent (still touches the whole struct)
    group.bench_function("AoS_SpikeScan_Equivalent", |b| {
        let mut state = next_brain::state::aos_baseline::AosStateBaseline::new(n);
        b.iter(|| {
            state.step_spikes_only(0);
        });
    });

    group.finish();
}

/// Comparison 3: Wake-up Density Stress Analysis.
fn bench_wake_up_stress(c: &mut Criterion) {
    let wake_up_counts = [10, 100];
    let mut group = c.benchmark_group("Wake_Up_Stress_SoA_vs_AoS");

    for &count in &wake_up_counts {
        let parameter = format!("events_{}", count);

        group.bench_function(BenchmarkId::new("SoA", &parameter), |b| {
            let (mut scheduler, active_ids) = setup_soa(0.01); // 1% base activity
            b.iter(|| {
                let slot = scheduler.current_slot;
                for &id in &active_ids {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: id,
                        target_slot: slot,
                        signal_strength: 0.1,
                    });
                }
                for i in 0..count {
                    let tid = ChunkId(i % NUM_CHUNKS as u32);
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: tid,
                        target_slot: slot,
                        signal_strength: 1.0,
                    });
                }
                scheduler.step();
            });
        });

        group.bench_function(BenchmarkId::new("AoS", &parameter), |b| {
            let (mut scheduler, active_ids) = setup_aos(0.01);
            b.iter(|| {
                let slot = scheduler.current_slot;
                for &id in &active_ids {
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: id,
                        target_slot: slot,
                        signal_strength: 0.1,
                    });
                }
                for i in 0..count {
                    let tid = ChunkId(i % NUM_CHUNKS as u32);
                    scheduler.inject_event(DelayedEvent {
                        target_chunk: tid,
                        target_slot: slot,
                        signal_strength: 1.0,
                    });
                }
                scheduler.step();
            });
        });
    }
    group.finish();
}

criterion_group!(
    benches,
    bench_sparsity_comparison,
    bench_crossover_scan,
    bench_selective_access,
    bench_wake_up_stress
);
criterion_main!(benches);
