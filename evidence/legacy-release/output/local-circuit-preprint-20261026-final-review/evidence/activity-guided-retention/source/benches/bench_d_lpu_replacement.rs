//! Benchmark D: LPU Replacement-Ratio Sweep (Task 6 – Paper 2 scaling benchmark).
//!
//! Three benchmark families, each measuring wall-clock time only.
//! Scientific resource metrics are reported by `examples/measure_lpu_resources.rs`.
//!
//! ## Family A — `LPU_Replacement_Sweep`
//! Topology fixed (balanced E/I, 500 units, 6 chunks).
//! Sweeps structural replacement ratio 0%→100%.
//! Ratio = real structural edge partition via `split_by_ratio`.
//!
//! ## Family B — `LPU_Scaling_Ladder`
//! Two loads:
//!   - `Driven`    (strength=2.0): sparse activity, tests aggregator overhead cost
//!   - `Sustained` (strength=10.0): high activity, surfaces event-queue bottleneck
//!     Sweeps scale 500→50 000 units, LPU 100% vs Explicit 0%.
//!
//! ## Family C — `LPU_BoundaryHeavy`
//! 1 000 units, `p_ei=0.80 p_ie=1.00 forbid_within_chunk=true`.
//! Adversarial cross-chunk topology. LPU gains tested under dense boundary traffic.
//!
//! ## Calibration
//! Before each LPU bench point the harness runs a calibration pass that adjusts
//! `AggregatorParams.gain_exc/gain_inh` (via bisection) so that LPU FR matches
//! explicit FR within 5%. This makes the wall-clock comparison scientifically fair
//! and prevents the FR artefact from polluting the timing signal.

use std::time::Duration;

use criterion::{BenchmarkId, Criterion, criterion_group, criterion_main};
use next_brain::connectivity::{
    event_router::EventRouter,
    microcircuit::{EIMicrocircuit, EIMicrocircuitSpec},
};
use next_brain::core::chunk::ChunkId;
use next_brain::experiment::{
    harness::{HarnessConfig, run_explicit, run_mixed},
    input_protocol::{InputProtocol, OperatingRegime},
    lpu_index::LpuTopologyIndex,
};
use next_brain::lpu::{
    aggregator::{AggregationMode, AggregatorParams},
    calibration::{CalibrationProbe, calibrate},
};

// ── Constants ──────────────────────────────────────────────────────────────────

const REPLACEMENT_RATIOS: &[f32] = &[0.0, 0.25, 0.50, 0.75, 1.0];

/// Scaling ladder: (exc_units, inh_units, units_per_chunk)
const SCALES: &[(usize, usize, usize)] = &[
    (400, 100, 100),         //    500 units,  5 chunks
    (2_000, 500, 100),       //  2 500 units, 25 chunks
    (8_000, 2_000, 100),     // 10 000 units,100 chunks
    (40_000, 10_000, 100),   // 50 000 units,500 chunks
    (400_000, 100_000, 100), //500 000 units, 5000 chunks
];

const NUM_STEPS: u64 = 200;

// ── Chunk-ID helpers ──────────────────────────────────────────────────────────

fn make_chunk_ids(exc_units: usize, inh_units: usize, upc: usize) -> (Vec<ChunkId>, Vec<ChunkId>) {
    let n_exc = exc_units.div_ceil(upc);
    let n_inh = inh_units.div_ceil(upc);
    let exc_ids: Vec<ChunkId> = (0..n_exc as u32).map(ChunkId).collect();
    let inh_ids: Vec<ChunkId> = (n_exc as u32..(n_exc + n_inh) as u32)
        .map(ChunkId)
        .collect();
    (exc_ids, inh_ids)
}

// ── Config helpers ────────────────────────────────────────────────────────────

fn explicit_config(
    exc_units: usize,
    inh_units: usize,
    upc: usize,
    mc: &EIMicrocircuit,
    exc_ids: &[ChunkId],
    n_chunks: usize,
    regime: OperatingRegime,
) -> HarnessConfig {
    let all_projs = mc.all_proj_refs();
    HarnessConfig {
        exc_units,
        inh_units,
        units_per_chunk: upc,
        dt: 0.001,
        num_steps: NUM_STEPS,
        input_protocol: InputProtocol::for_regime(regime, exc_ids.to_vec()),
        router: Some(EventRouter::from_projections(&all_projs, n_chunks)),
        lpu_params: AggregatorParams::default(),
        replaced_circuit: None,
        lpu_index: None,
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
    }
}

/// Build a calibrated mixed config.
///
/// Runs an explicit reference pass, then bisects `gain_exc/gain_inh` so that
/// LPU FR matches explicit FR within 5%. This ensures the wall-clock comparison
/// is not confounded by unmatched firing rates.
#[allow(clippy::too_many_arguments)]
fn calibrated_mixed_config(
    exc_units: usize,
    inh_units: usize,
    upc: usize,
    full_mc: &EIMicrocircuit,
    ratio: f32,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
    n_chunks: usize,
    regime: OperatingRegime,
) -> HarnessConfig {
    // 1. Build structural split.
    let (explicit_mc, lpu_mc) = full_mc.split_by_ratio(ratio, 42);
    let lpu_index = LpuTopologyIndex::build(&lpu_mc, n_chunks);

    // 2. Explicit reference run at same regime.
    let explicit_ref = explicit_config(
        exc_units, inh_units, upc, full_mc, exc_ids, n_chunks, regime,
    );
    let explicit_rec = run_explicit(&explicit_ref);
    let explicit_probe = CalibrationProbe {
        mean_firing_rate: explicit_rec.mean_firing_rate(),
        mean_g_exc: 0.0,
        mean_g_inh: 0.0,
    };

    // 3. Build LPU config builder closure for the calibrator.
    let all_projs2 = explicit_mc.all_proj_refs();
    let router = if explicit_mc.total_edge_count() > 0 {
        Some(EventRouter::from_projections(&all_projs2, n_chunks))
    } else {
        None
    };

    // Clone lpu_mc for calibration probe runs.
    let (_, lpu_mc_for_cal) = full_mc.split_by_ratio(ratio, 42);
    let cal_result = calibrate(
        &explicit_probe,
        |params: &AggregatorParams| {
            // Build a fresh index for each calibration probe (small overhead, fine for setup).
            let (_, lpu_mc_inner) = full_mc.split_by_ratio(ratio, 42);
            let idx = LpuTopologyIndex::build(&lpu_mc_inner, n_chunks);
            let mut cfg = HarnessConfig {
                exc_units,
                inh_units,
                units_per_chunk: upc,
                dt: 0.001,
                num_steps: 50, // short calibration run
                input_protocol: InputProtocol::for_regime(regime, exc_ids.to_vec()),
                router: None, // pure LPU for calibration
                lpu_params: params.clone(),
                replaced_circuit: Some(lpu_mc_inner),
                lpu_index: Some(idx),
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
            };
            let rec = run_mixed(&mut cfg, exc_ids, inh_ids);
            CalibrationProbe {
                mean_firing_rate: rec.mean_firing_rate(),
                mean_g_exc: 0.0,
                mean_g_inh: 0.0,
            }
        },
        AggregationMode::NormalizedRate,
        0.05, // 5% tolerance
        12,   // max bisection iters
    );

    let _ = lpu_mc_for_cal; // drop

    HarnessConfig {
        exc_units,
        inh_units,
        units_per_chunk: upc,
        dt: 0.001,
        num_steps: NUM_STEPS,
        input_protocol: InputProtocol::for_regime(regime, exc_ids.to_vec()),
        router,
        lpu_params: cal_result.params,
        replaced_circuit: Some(lpu_mc),
        lpu_index: Some(lpu_index),
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
    }
}

// ── Family A: Replacement-Ratio Sweep ─────────────────────────────────────────

fn bench_replacement_ratio(c: &mut Criterion) {
    let (exc_units, inh_units, upc) = (400, 100, 100);
    let (exc_ids, inh_ids) = make_chunk_ids(exc_units, inh_units, upc);
    let n_chunks = exc_ids.len() + inh_ids.len();
    let full_mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();

    let mut group = c.benchmark_group("LPU_Replacement_Sweep");

    for &ratio in REPLACEMENT_RATIOS {
        let label = format!("ratio_{:.0}pct", ratio * 100.0);

        if ratio == 0.0 {
            let cfg = explicit_config(
                exc_units,
                inh_units,
                upc,
                &full_mc,
                &exc_ids,
                n_chunks,
                OperatingRegime::Driven,
            );
            group.bench_with_input(BenchmarkId::new("Explicit", &label), &label, |b, _| {
                b.iter(|| criterion::black_box(run_explicit(&cfg).total_events()))
            });
        } else {
            let mut cfg = calibrated_mixed_config(
                exc_units,
                inh_units,
                upc,
                &full_mc,
                ratio,
                &exc_ids,
                &inh_ids,
                n_chunks,
                OperatingRegime::Driven,
            );
            group.bench_with_input(BenchmarkId::new("Mixed", &label), &label, |b, _| {
                b.iter(|| {
                    criterion::black_box(run_mixed(&mut cfg, &exc_ids, &inh_ids).total_events())
                })
            });
        }
    }
    group.finish();
}

// ── Family B: Scaling Ladder ───────────────────────────────────────────────────

fn bench_scaling_ladder(c: &mut Criterion) {
    let mut group = c.benchmark_group("LPU_Scaling_Ladder");

    for &regime in &[OperatingRegime::Driven, OperatingRegime::Sustained] {
        let load_label = match regime {
            OperatingRegime::Driven => "Driven",
            OperatingRegime::Sustained => "Sustained",
            OperatingRegime::Quiescent => "Quiescent",
        };

        for &(exc_units, inh_units, upc) in SCALES {
            let total_units = exc_units + inh_units;
            let (exc_ids, inh_ids) = make_chunk_ids(exc_units, inh_units, upc);
            let n_chunks = exc_ids.len() + inh_ids.len();
            let label = format!("{}_{}_{}u_{}c", load_label, "0pct", total_units, n_chunks);

            // Tiered sampling: large-scale points need more time to converge
            // confidence intervals to < 5% relative width for paper citation.
            match total_units {
                n if n >= 500_000 => {
                    group.sample_size(10);
                    group.warm_up_time(Duration::from_secs(10));
                    group.measurement_time(Duration::from_secs(120));
                }
                n if n >= 50_000 => {
                    group.sample_size(20);
                    group.warm_up_time(Duration::from_secs(5));
                    group.measurement_time(Duration::from_secs(60));
                }
                n if n >= 10_000 => {
                    group.sample_size(30);
                    group.warm_up_time(Duration::from_secs(3));
                    group.measurement_time(Duration::from_secs(20));
                }
                _ => {
                    group.sample_size(100);
                    group.warm_up_time(Duration::from_secs(3));
                }
            }

            let full_mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();

            // Explicit (ratio=0)
            {
                let cfg = explicit_config(
                    exc_units, inh_units, upc, &full_mc, &exc_ids, n_chunks, regime,
                );
                let expl_label = format!("Explicit/{}/{}", load_label, total_units);
                group.bench_with_input(
                    BenchmarkId::from_parameter(&expl_label),
                    &expl_label,
                    |b, _| b.iter(|| criterion::black_box(run_explicit(&cfg).total_events())),
                );
            }

            // LPU 100% — calibrated
            {
                let mut cfg = calibrated_mixed_config(
                    exc_units, inh_units, upc, &full_mc, 1.0, &exc_ids, &inh_ids, n_chunks, regime,
                );
                let lpu_label = format!("LPU/{}/{}", load_label, total_units);
                group.bench_with_input(
                    BenchmarkId::from_parameter(&lpu_label),
                    &lpu_label,
                    |b, _| {
                        b.iter(|| {
                            criterion::black_box(
                                run_mixed(&mut cfg, &exc_ids, &inh_ids).total_events(),
                            )
                        })
                    },
                );
            }

            let _ = label;
        }
    }
    group.finish();
}

// ── Family C: Boundary-Heavy Topology ─────────────────────────────────────────

fn bench_boundary_heavy(c: &mut Criterion) {
    let (exc_units, inh_units, upc) = (800, 200, 100);
    let (exc_ids, inh_ids) = make_chunk_ids(exc_units, inh_units, upc);
    let n_chunks = exc_ids.len() + inh_ids.len();

    let mc = EIMicrocircuitSpec {
        p_ee: 0.05,
        p_ei: 0.80,
        p_ie: 1.00,
        p_ii: 0.10,
        forbid_within_chunk: true,
        ..EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone())
    }
    .build();

    let mut group = c.benchmark_group("LPU_BoundaryHeavy");

    for &ratio in REPLACEMENT_RATIOS {
        let label = format!("ratio_{:.0}pct", ratio * 100.0);

        if ratio == 0.0 {
            let cfg = explicit_config(
                exc_units,
                inh_units,
                upc,
                &mc,
                &exc_ids,
                n_chunks,
                OperatingRegime::Sustained,
            );
            group.bench_with_input(BenchmarkId::new("Explicit", &label), &label, |b, _| {
                b.iter(|| criterion::black_box(run_explicit(&cfg).total_events()))
            });
        } else {
            let mut cfg = calibrated_mixed_config(
                exc_units,
                inh_units,
                upc,
                &mc,
                ratio,
                &exc_ids,
                &inh_ids,
                n_chunks,
                OperatingRegime::Sustained,
            );
            group.bench_with_input(BenchmarkId::new("Mixed", &label), &label, |b, _| {
                b.iter(|| {
                    criterion::black_box(run_mixed(&mut cfg, &exc_ids, &inh_ids).total_events())
                })
            });
        }
    }
    group.finish();
}

// ── Criterion entry ────────────────────────────────────────────────────────────

criterion_group!(
    benches,
    bench_replacement_ratio,
    bench_scaling_ladder,
    bench_boundary_heavy
);
criterion_main!(benches);
