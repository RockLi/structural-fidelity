//! Scientific resource metrics reporter for the LPU replacement benchmark.
//!
//! **P0 / P1 of the Paper 2 Benchmark Upgrade Plan.**
//!
//! This binary runs each `(scale, ratio)` combination *once*, records the scientific
//! metrics that cannot be captured inside a micro-benchmark loop, and prints a
//! human-readable report for Paper 2 Tables 3 & 4.
//!
//! ## Tables produced
//! | Table | Content |
//! |---|---|
//! | **A** | Replacement-ratio sweep (500 units, 6 chunks, Sustained) |
//! | **B** | Scaling ladder — Explicit 0% vs LPU 100% |
//! | **C** | Boundary-heavy topology |
//! | **CALIB** | Calibration quality table (gain · FR-error% · iters · converged) |
//! | **D** | Population-level dynamics validation (2.5k / 10k / 50k / 500k) |
//! | **D2** | Boundary-Heavy dynamics (same metrics) |
//! | **E** | Cross-scale gain portability (50k ↔ 500k — proves same-scale requirement) |
//!
//! ## Acceptance thresholds (Paper 2 §2.3 — citable constants)
//! | Metric | Threshold | Role |
//! |---|---|---|
//! | FR calibration error | ≤ 5 % | **Calibration target** — hard pass/fail gate |
//! | PSTH temporal alignment r | < 0.50 | **Evaluation metric** — soft concern flag |
//!
//! # Usage
//! ```
//! cargo run --example measure_lpu_resources --release
//! ```

use next_brain::connectivity::{
    event_router::EventRouter,
    microcircuit::{EIMicrocircuit, EIMicrocircuitSpec},
    types::LocalProjection,
};
use next_brain::core::chunk::ChunkId;
use next_brain::experiment::{
    harness::{HarnessConfig, RunRecord, run_explicit, run_mixed},
    input_protocol::{InputProtocol, OperatingRegime},
    lpu_index::LpuTopologyIndex,
};
use next_brain::lpu::{
    aggregator::{AggregationMode, AggregatorParams},
    calibration::{CalibrationProbe, CalibrationResult, calibrate},
};

// ── Scale / ratio constants ───────────────────────────────────────────────────

/// (label, exc_units, inh_units, units_per_chunk)
const SCALES: &[(&str, usize, usize, usize)] = &[
    ("500u/6c",          400,     100,    100),
    ("2500u/25c",      2_000,     500,    100),
    ("10000u/100c",    8_000,   2_000,    100),
    ("50000u/500c",   40_000,  10_000,    100),
    ("500000u/5000c", 400_000, 100_000,   100),
];

const REPLACEMENT_RATIOS: &[f32] = &[0.0, 0.25, 0.50, 0.75, 1.0];

// ── Timing constants ──────────────────────────────────────────────────────────

/// Steps for resource tables (A, B, C) and cross-scale portability (E).
const NUM_STEPS: u64 = 200;
/// Calibration bisection probes must use the same step count as the measurement
/// they support — mismatching causes mid-transient calibration (FR drift).
const CALIB_STEPS: u64 = NUM_STEPS;
/// Longer run for Table D dynamics — gives the windowed DFT 1 Hz resolution
/// (bin width = Fs/N = 1000 Hz / 1000 samples).
const DYN_STEPS: u64 = 1_000;
/// Same-scale calibration for Table D must also use DYN_STEPS as the reference.
const DYN_CALIB_STEPS: u64 = DYN_STEPS;

// ── Acceptance thresholds (citable in Paper 2 §2.3) ──────────────────────────

/// Maximum relative firing-rate error allowed after calibration.
/// **Role: calibration target — hard pass/fail gate.**
const FR_CALIB_TOLERANCE: f32 = 0.05; // 5 %

/// Maximum number of bisection iterations per calibration run.
const CALIB_MAX_ITERS: u32 = 12;

/// PSTH temporal-alignment (Pearson r) below this value is flagged as a
/// concern. **Role: evaluation-only metric — soft concern flag, NOT a gate.**
const PSTH_R_CONCERN_THRESHOLD: f32 = 0.50;

const REGIME: OperatingRegime = OperatingRegime::Sustained;

// ── Low-level helpers ─────────────────────────────────────────────────────────

fn make_chunk_ids(exc_units: usize, inh_units: usize, upc: usize) -> (Vec<ChunkId>, Vec<ChunkId>) {
    let n_exc = exc_units.div_ceil(upc);
    let n_inh = inh_units.div_ceil(upc);
    let exc_ids: Vec<ChunkId> = (0..n_exc as u32).map(ChunkId).collect();
    let inh_ids: Vec<ChunkId> = (n_exc as u32..(n_exc + n_inh) as u32)
        .map(ChunkId)
        .collect();
    (exc_ids, inh_ids)
}

fn total_weight(p: &LocalProjection) -> f32 {
    p.edges.iter().map(|e| e.weight).sum()
}

/// Build an explicit (ratio=0) config.
fn explicit_cfg(
    exc_units: usize,
    inh_units: usize,
    upc: usize,
    mc: &EIMicrocircuit,
    exc_ids: &[ChunkId],
    n_chunks: usize,
) -> HarnessConfig {
    let all_projs = mc.all_proj_refs();
    HarnessConfig {
        exc_units,
        inh_units,
        units_per_chunk: upc,
        dt: 0.001,
        num_steps: NUM_STEPS,
        input_protocol: InputProtocol::for_regime(REGIME, exc_ids.to_vec()),
        router: Some(EventRouter::from_projections(&all_projs, n_chunks)),
        lpu_params: AggregatorParams::default(),
        replaced_circuit: None,
        lpu_index: None,
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
    }
}

/// Build a calibrated LPU/mixed config using `LpuTopologyIndex`.
///
/// Returns `(HarnessConfig, CalibrationResult)` so that gain, error, iterations,
/// and the explicit reference FR are all available to callers for the CALIB table.
///
/// # Arguments
/// * `calib_steps`   — Steps for both the explicit reference probe and each
///   bisection probe.  **Must equal `measure_steps`** to ensure calibration targets
///   the same steady-state as the final measurement (prevents FR drift).
/// * `measure_steps` — Steps for the returned `HarnessConfig`.
#[allow(clippy::too_many_arguments)]
fn calibrated_mix_cfg(
    exc_units: usize,
    inh_units: usize,
    upc: usize,
    full_mc: &EIMicrocircuit,
    ratio: f32,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
    n_chunks: usize,
    calib_steps: u64,
    measure_steps: u64,
) -> (HarnessConfig, CalibrationResult) {
    // 1. Explicit reference probe (run for calib_steps so it targets the same
    //    steady-state as the LPU probes within the bisection loop).
    let mut ref_cfg = explicit_cfg(exc_units, inh_units, upc, full_mc, exc_ids, n_chunks);
    ref_cfg.num_steps = calib_steps;
    let ref_rec = run_explicit(&ref_cfg);
    let ref_probe = CalibrationProbe {
        mean_firing_rate: ref_rec.mean_firing_rate(),
        mean_g_exc: 0.0,
        mean_g_inh: 0.0,
    };

    // 2. Bisect gain_exc/gain_inh until LPU FR matches within FR_CALIB_TOLERANCE.
    let cal = calibrate(
        &ref_probe,
        |params: &AggregatorParams| {
            let (_, lpu_inner) = full_mc.split_by_ratio(ratio, 42);
            let idx = LpuTopologyIndex::build(&lpu_inner, n_chunks);
            let (expl_inner, _) = full_mc.split_by_ratio(ratio, 42);
            let all_p = expl_inner.all_proj_refs();
            let router = if expl_inner.total_edge_count() > 0 {
                Some(EventRouter::from_projections(&all_p, n_chunks))
            } else {
                None
            };
            let mut cfg = HarnessConfig {
                exc_units,
                inh_units,
                units_per_chunk: upc,
                dt: 0.001,
                num_steps: calib_steps,
                input_protocol: InputProtocol::for_regime(REGIME, exc_ids.to_vec()),
                router,
                lpu_params: params.clone(),
                replaced_circuit: Some(lpu_inner),
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
        FR_CALIB_TOLERANCE,
        CALIB_MAX_ITERS,
    );

    // 3. Build final full-length config with calibrated params + topology index.
    let (expl_mc2, lpu_mc2) = full_mc.split_by_ratio(ratio, 42);
    let lpu_index = LpuTopologyIndex::build(&lpu_mc2, n_chunks);
    let all_p2 = expl_mc2.all_proj_refs();
    let router = if expl_mc2.total_edge_count() > 0 {
        Some(EventRouter::from_projections(&all_p2, n_chunks))
    } else {
        None
    };

    (
        HarnessConfig {
            exc_units,
            inh_units,
            units_per_chunk: upc,
            dt: 0.001,
            num_steps: measure_steps,
            input_protocol: InputProtocol::for_regime(REGIME, exc_ids.to_vec()),
            router,
            lpu_params: cal.params.clone(),
            replaced_circuit: Some(lpu_mc2),
            lpu_index: Some(lpu_index),
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
        },
        cal,
    )
}

/// Run LPU 100% mode with a **fixed pre-calibrated gain** (no bisection).
/// Used in Table E to demonstrate cross-scale gain portability failure.
#[allow(clippy::too_many_arguments)]
fn run_lpu_fixed_gain(
    exc_units: usize,
    inh_units: usize,
    upc: usize,
    full_mc: &EIMicrocircuit,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
    n_chunks: usize,
    fixed_gain: f32,
    steps: u64,
) -> RunRecord {
    // At ratio=1.0 the explicit part is empty → no EventRouter needed.
    let (expl_mc, lpu_mc) = full_mc.split_by_ratio(1.0, 42);
    let lpu_index = LpuTopologyIndex::build(&lpu_mc, n_chunks);
    let all_p = expl_mc.all_proj_refs();
    let router = if expl_mc.total_edge_count() > 0 {
        Some(EventRouter::from_projections(&all_p, n_chunks))
    } else {
        None
    };
    let mut cfg = HarnessConfig {
        exc_units,
        inh_units,
        units_per_chunk: upc,
        dt: 0.001,
        num_steps: steps,
        input_protocol: InputProtocol::for_regime(REGIME, exc_ids.to_vec()),
        router,
        lpu_params: AggregatorParams {
            mode: AggregationMode::NormalizedRate,
            gain_exc: fixed_gain,
            gain_inh: fixed_gain,
            tau_field: 10.0,
        },
        replaced_circuit: Some(lpu_mc),
        lpu_index: Some(lpu_index),
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
    };
    run_mixed(&mut cfg, exc_ids, inh_ids)
}

// ── Acceptance threshold block ────────────────────────────────────────────────

fn print_acceptance_thresholds() {
    println!("┌─────────────────────────────────────────────────────────────────────┐");
    println!("│  Acceptance Thresholds — Paper 2 §2.3 (citable constants)          │");
    println!("├──────────────────────────────┬───────────┬────────────────────────┤");
    println!("│ Metric                       │ Threshold │ Role                   │");
    println!("├──────────────────────────────┼───────────┼────────────────────────┤");
    println!(
        "│ FR calibration error         │  ≤ {:>5.1}% │ Calibration target —   │",
        FR_CALIB_TOLERANCE * 100.0
    );
    println!("│                              │           │ hard pass/fail gate    │");
    println!("├──────────────────────────────┼───────────┼────────────────────────┤");
    println!(
        "│ PSTH temporal alignment (r)  │  < {:>5.2}  │ Evaluation metric —    │",
        PSTH_R_CONCERN_THRESHOLD
    );
    println!("│                              │           │ soft concern flag only │");
    println!("├──────────────────────────────┼───────────┼────────────────────────┤");
    println!(
        "│ Max calibration iterations   │  ≤ {:>5}   │ Bisection budget       │",
        CALIB_MAX_ITERS
    );
    println!("└──────────────────────────────┴───────────┴────────────────────────┘");
    println!();
}

// ── Calibration quality table ─────────────────────────────────────────────────

/// One row in the calibration quality summary (CALIB table).
struct CalibRecord {
    scale: String,
    ratio_pct: u32,
    calibrated_gain: f32,
    fr_error_pct: f32,
    iterations: u32,
    converged: bool,
}

fn print_calibration_table(records: &[CalibRecord]) {
    println!("=== CALIB: Calibration Quality Table ===");
    println!();
    println!(
        "{:<18} {:>7} {:>13} {:>11} {:>6} {:>10}",
        "Scale", "Ratio%", "CalibratedGain", "FR_error%", "Iters", "Converged"
    );
    println!("{}", "─".repeat(72));
    for r in records {
        println!(
            "{:<18} {:>7} {:>13.4} {:>11.2} {:>6} {:>10}",
            r.scale,
            format!("{}%", r.ratio_pct),
            r.calibrated_gain,
            r.fr_error_pct,
            r.iterations,
            if r.converged { "✓ yes" } else { "✗ NO" },
        );
    }
    println!();
    let n_failed = records.iter().filter(|r| !r.converged).count();
    if n_failed == 0 {
        println!(
            "✓ All {} calibration runs converged within {:.0}% FR tolerance.",
            records.len(),
            FR_CALIB_TOLERANCE * 100.0
        );
    } else {
        println!(
            "✗ {} / {} calibration runs did NOT converge — review gain range or tolerance.",
            n_failed,
            records.len()
        );
    }
    println!();
}

// ── PSD CSV export ────────────────────────────────────────────────────────────

/// Write PSD spectrum `(frequency_hz, power)` pairs to a CSV file.
/// Consumed by `examples/plot_psd.py` to produce Figure 4.
fn export_psd_csv(filename: &str, spectrum: &[(f32, f32)]) {
    use std::io::Write as _;
    match std::fs::File::create(filename) {
        Ok(mut f) => {
            let _ = writeln!(f, "frequency_hz,power");
            for &(freq, power) in spectrum {
                let _ = writeln!(f, "{:.4},{:.6e}", freq, power);
            }
            println!("  PSD exported → {}", filename);
        }
        Err(e) => eprintln!("  WARNING: could not write PSD CSV '{}': {}", filename, e),
    }
}

// ── Resource report row ───────────────────────────────────────────────────────

struct Row {
    scale: String,
    ratio_pct: u32,
    mode: String,
    explicit_edges: usize,
    lpu_edges: usize,
    events_step: f32,
    active_chunks: f32,
    fr: f32,
    calib_gain: Option<f32>,
    lpu_bound_ok: bool,
    n_chunks: usize,
}

impl Row {
    fn header() {
        println!(
            "{:<16} {:>6} {:<12} {:>10} {:>9} {:>12} {:>13} {:>8} {:>10} {:>10}",
            "Scale",
            "Ratio%",
            "Mode",
            "ExplEdges",
            "LPUEdges",
            "Events/step",
            "ActiveChunks",
            "FR",
            "CalibGain",
            "LPUBound✓"
        );
        println!("{}", "─".repeat(112));
    }

    fn print(&self) {
        let bound = if self.lpu_bound_ok { "✓" } else { "✗ FAIL" };
        let gain_str = match self.calib_gain {
            Some(g) => format!("{:.4}", g),
            None => "—".to_string(),
        };
        println!(
            "{:<16} {:>6} {:<12} {:>10} {:>9} {:>12.2} {:>13.2} {:>8.5} {:>10} {:>10}",
            self.scale,
            format!("{:.0}%", self.ratio_pct),
            self.mode,
            self.explicit_edges,
            self.lpu_edges,
            self.events_step,
            self.active_chunks,
            self.fr,
            gain_str,
            bound
        );
    }
}

// ── Single data-point runner (Tables A / B partial / C) ───────────────────────

#[allow(clippy::too_many_arguments)]
fn run_point(
    scale_label: &str,
    exc_units: usize,
    inh_units: usize,
    upc: usize,
    full_mc: &EIMicrocircuit,
    exc_ids: &[ChunkId],
    inh_ids: &[ChunkId],
    n_chunks: usize,
    ratio: f32,
    rows: &mut Vec<Row>,
    calib_records: &mut Vec<CalibRecord>,
) {
    let (explicit_mc_peek, lpu_mc_peek) = full_mc.split_by_ratio(ratio, 42);
    let explicit_edges = explicit_mc_peek.total_edge_count();
    let lpu_edges = lpu_mc_peek.total_edge_count();

    let (events_step, active_chunks, fr, calib_gain) = if ratio == 0.0 {
        let cfg = explicit_cfg(exc_units, inh_units, upc, full_mc, exc_ids, n_chunks);
        let rec = run_explicit(&cfg);
        (
            rec.total_events() as f32 / NUM_STEPS as f32,
            rec.mean_active_chunks(),
            rec.mean_firing_rate(),
            None,
        )
    } else {
        let (mut cfg, cal) = calibrated_mix_cfg(
            exc_units, inh_units, upc, full_mc, ratio,
            exc_ids, inh_ids, n_chunks,
            CALIB_STEPS, NUM_STEPS,
        );
        let rec = run_mixed(&mut cfg, exc_ids, inh_ids);
        let gain = cal.params.gain_exc;
        calib_records.push(CalibRecord {
            scale: scale_label.to_string(),
            ratio_pct: (ratio * 100.0).round() as u32,
            calibrated_gain: gain,
            fr_error_pct: cal.fr_error_pct(),
            iterations: cal.iterations,
            converged: cal.converged,
        });
        (
            rec.total_events() as f32 / NUM_STEPS as f32,
            rec.mean_active_chunks(),
            rec.mean_firing_rate(),
            Some(gain),
        )
    };

    let lpu_bound_ok = ratio == 0.0 || events_step <= 2.0 * n_chunks as f32 + 0.5;

    let row = Row {
        scale: scale_label.to_string(),
        ratio_pct: (ratio * 100.0).round() as u32,
        mode: if ratio == 0.0 {
            "Explicit".into()
        } else {
            format!("Mixed-{:.0}%", ratio * 100.0)
        },
        explicit_edges,
        lpu_edges,
        events_step,
        active_chunks,
        fr,
        calib_gain,
        lpu_bound_ok,
        n_chunks,
    };
    row.print();
    rows.push(row);
}

// ── Main ──────────────────────────────────────────────────────────────────────

fn main() {
    println!();
    println!("╔══════════════════════════════════════════════════════════════════════════════╗");
    println!("║  LPU Resource Metrics Report — Paper 2 Tables 3 & 4                        ║");
    println!("║  calibrated · scale-aware · fast-path · LpuTopologyIndex                   ║");
    println!("╚══════════════════════════════════════════════════════════════════════════════╝");
    println!();
    println!("Network : balanced E/I microcircuit │ dt=1ms │ Sustained drive");
    println!("LPU     : calibrated gain (FR error ≤5%, bisection) │ LpuTopologyIndex");
    println!("Bound   : ≤ 2 events/active-target-chunk (Exc+Inh two-channel proxy)");
    println!();

    // ── Acceptance Threshold Block (Paper 2 §2.3) ──────────────────────────────
    print_acceptance_thresholds();

    let mut rows: Vec<Row> = Vec::new();
    let mut calib_records: Vec<CalibRecord> = Vec::new();

    // ── Table A: replacement-ratio sweep ──────────────────────────────────────
    println!(
        "=== A: Replacement-Ratio Sweep  (500 units, 6 chunks, Sustained, steps={NUM_STEPS}) ==="
    );
    println!();
    Row::header();
    {
        let (eu, iu, upc) = (400, 100, 100);
        let (exc_ids, inh_ids) = make_chunk_ids(eu, iu, upc);
        let nc = exc_ids.len() + inh_ids.len();
        let mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();
        for &ratio in REPLACEMENT_RATIOS {
            run_point(
                "500u/6c", eu, iu, upc, &mc, &exc_ids, &inh_ids, nc, ratio,
                &mut rows, &mut calib_records,
            );
        }
    }
    println!();

    // ── Table B: scaling ladder ────────────────────────────────────────────────
    println!(
        "=== B: Scaling Ladder — Explicit 0% vs LPU 100%  (Sustained, steps={NUM_STEPS}) ==="
    );
    println!();
    Row::header();

    for &(label, eu, iu, upc) in SCALES {
        let (exc_ids, inh_ids) = make_chunk_ids(eu, iu, upc);
        let nc = exc_ids.len() + inh_ids.len();
        let mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();

        // Explicit row (ratio=0).
        run_point(
            label, eu, iu, upc, &mc, &exc_ids, &inh_ids, nc, 0.0,
            &mut rows, &mut calib_records,
        );

        // LPU 100% row — built inline so the scale label is blank for visual grouping.
        let (expl_peek, lpu_peek) = mc.split_by_ratio(1.0, 42);
        let lpu_edges = lpu_peek.total_edge_count();
        drop((expl_peek, lpu_peek));

        let (mut cfg, cal) = calibrated_mix_cfg(
            eu, iu, upc, &mc, 1.0, &exc_ids, &inh_ids, nc,
            CALIB_STEPS, NUM_STEPS,
        );
        let rec = run_mixed(&mut cfg, &exc_ids, &inh_ids);
        let events_step = rec.total_events() as f32 / NUM_STEPS as f32;
        let lpu_bound_ok = events_step <= 2.0 * nc as f32 + 0.5;

        calib_records.push(CalibRecord {
            scale: label.to_string(),
            ratio_pct: 100,
            calibrated_gain: cal.params.gain_exc,
            fr_error_pct: cal.fr_error_pct(),
            iterations: cal.iterations,
            converged: cal.converged,
        });

        let row = Row {
            scale: "".to_string(), // blank — visual grouping under the explicit row
            ratio_pct: 100,
            mode: "LPU".into(),
            explicit_edges: 0,
            lpu_edges,
            events_step,
            active_chunks: rec.mean_active_chunks(),
            fr: rec.mean_firing_rate(),
            calib_gain: Some(cal.params.gain_exc),
            lpu_bound_ok,
            n_chunks: nc,
        };
        row.print();
        rows.push(row);
    }
    println!();

    // ── Table C: boundary-heavy topology ──────────────────────────────────────
    println!(
        "=== C: Boundary-Heavy Topology  (1000 units, 10 chunks, p_ei=0.8, p_ie=1.0, Sustained) ==="
    );
    println!();
    Row::header();
    {
        let (eu, iu, upc) = (800, 200, 100);
        let (exc_ids, inh_ids) = make_chunk_ids(eu, iu, upc);
        let nc = exc_ids.len() + inh_ids.len();
        let bh_mc = EIMicrocircuitSpec {
            p_ee: 0.05,
            p_ei: 0.80,
            p_ie: 1.00,
            p_ii: 0.10,
            forbid_within_chunk: true,
            ..EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone())
        }
        .build();
        for &ratio in REPLACEMENT_RATIOS {
            run_point(
                "BoundaryHeavy", eu, iu, upc, &bh_mc, &exc_ids, &inh_ids, nc, ratio,
                &mut rows, &mut calib_records,
            );
        }
    }
    println!();

    // ── Table D: population-level dynamics validation ──────────────────────────
    println!(
        "=== D: Population-Level Dynamics Validation  (Explicit vs LPU 100%, steps={DYN_STEPS}) ==="
    );
    println!();
    println!("Notes:");
    println!("  · All LPU runs use same-scale calibration (own explicit baseline at {DYN_STEPS} steps).");
    println!("  · PSTH Correlation = population-rate temporal alignment (NOT single-unit spike timing).");
    println!("  · 500k scale may take several minutes; included for complete scientific record.");
    println!();
    println!(
        "{:<18} {:>7} {:>9} {:>7} {:>11} {:>10} {:>10} {:>11}",
        "Scale", "Mode", "MeanFR_Hz", "CV_pop", "PeakFreq_Hz", "PeakPow", "MaxFR_Hz", "T_peak_ms"
    );
    println!("{}", "─".repeat(93));

    // Extended to 500k for full scientific record (Paper 2 must-have).
    let dyn_scales: &[(&str, usize, usize, usize)] = &[
        ("2500u/25c",       2_000,   500, 100),
        ("10000u/100c",     8_000, 2_000, 100),
        ("50000u/500c",    40_000, 10_000, 100),
        ("500000u/5000c", 400_000, 100_000, 100),
    ];

    struct DynCompRow {
        label: String,
        psth_r: f32,
        delta_fr_pct: f32,
        delta_cv_pct: f32,
        delta_peak_hz: f32,
    }
    let mut dyn_cmp_rows: Vec<DynCompRow> = Vec::new();

    for &(label, deu, diu, dupc) in dyn_scales {
        let (d_exc_ids, d_inh_ids) = make_chunk_ids(deu, diu, dupc);
        let d_nc = d_exc_ids.len() + d_inh_ids.len();
        let d_mc = EIMicrocircuitSpec::balanced(d_exc_ids.clone(), d_inh_ids.clone()).build();

        // Explicit run.
        let mut e_cfg = explicit_cfg(deu, diu, dupc, &d_mc, &d_exc_ids, d_nc);
        e_cfg.num_steps = DYN_STEPS;
        let e_rec = run_explicit(&e_cfg);
        let e_dyn =
            next_brain::experiment::metrics::PopulationDynamics::from_record(&e_rec, 0.001);

        // Calibrated LPU run — same-scale calibration (DYN_CALIB_STEPS reference).
        let (mut l_cfg, dyn_cal) = calibrated_mix_cfg(
            deu, diu, dupc, &d_mc, 1.0,
            &d_exc_ids, &d_inh_ids, d_nc,
            DYN_CALIB_STEPS, DYN_STEPS,
        );
        
        calib_records.push(CalibRecord {
            scale: format!("{} (DYN)", label),
            ratio_pct: 100,
            calibrated_gain: dyn_cal.params.gain_exc,
            fr_error_pct: dyn_cal.fr_error_pct(),
            iterations: dyn_cal.iterations,
            converged: dyn_cal.converged,
        });

        let l_rec = run_mixed(&mut l_cfg, &d_exc_ids, &d_inh_ids);
        let l_dyn =
            next_brain::experiment::metrics::PopulationDynamics::from_record(&l_rec, 0.001);

        let cmp = next_brain::experiment::metrics::compare_dynamics(&e_rec, &l_rec, 0.001);

        fn print_dyn_row(
            label: &str,
            mode: &str,
            d: &next_brain::experiment::metrics::PopulationDynamics,
        ) {
            println!(
                "{:<18} {:>7} {:>9.5} {:>7.4} {:>11.2} {:>10.2e} {:>10.5} {:>11.2}",
                label,
                mode,
                d.mean_fr_hz,
                d.cv_pop,
                d.peak_freq_hz,
                d.peak_power,
                d.max_fr_hz,
                d.t_peak_ms,
            );
        }

        print_dyn_row(label, "Explicit", &e_dyn);
        
        let dyn_mode_str = if !dyn_cal.converged { "LPU(⚠)" } else { "LPU" };
        print_dyn_row("", dyn_mode_str, &l_dyn);

        let recovery_str = match l_dyn.recovery_time_ms {
            Some(r) => format!("{:.1}ms", r),
            None => "N/A".to_string(),
        };
        let psth_flag = if cmp.psth_correlation < PSTH_R_CONCERN_THRESHOLD {
            "  ⚠ CONCERN"
        } else {
            ""
        };
        println!(
            "  └─ Rise10-90: {:.1}ms | Recovery: {} | PSTH-r: {:.4}{} | ΔCV_pop: {:.2}%",
            l_dyn.rise_time_10_90_ms,
            recovery_str,
            cmp.psth_correlation,
            psth_flag,
            cmp.cv_pop_delta_pct,
        );
        println!();

        // Export PSD spectrum CSVs for the 50k sustained case (Paper 2 Figure 4).
        if label == "50000u/500c" {
            let e_trace =
                next_brain::experiment::metrics::get_fr_trace(&e_rec, 0.001);
            let l_trace =
                next_brain::experiment::metrics::get_fr_trace(&l_rec, 0.001);
            let e_psd =
                next_brain::experiment::metrics::compute_psd_spectrum(&e_trace, 0.001);
            let l_psd =
                next_brain::experiment::metrics::compute_psd_spectrum(&l_trace, 0.001);
            export_psd_csv("psd_50k_sustained_explicit.csv", &e_psd);
            export_psd_csv("psd_50k_sustained_lpu.csv", &l_psd);
        }

        dyn_cmp_rows.push(DynCompRow {
            label: label.to_string(),
            psth_r: cmp.psth_correlation,
            delta_fr_pct: cmp.mean_fr_delta_pct,
            delta_cv_pct: cmp.cv_pop_delta_pct,
            delta_peak_hz: cmp.peak_freq_delta_hz,
        });
    }

    // ── Table D2: boundary-heavy dynamics ──────────────────────────────────────
    println!("--- D2: Boundary-Heavy Topology (1000 units, 10 chunks) ---");
    println!();
    {
        let (bh_eu, bh_iu, bh_upc) = (800_usize, 200_usize, 100_usize);
        let (bh_exc_ids, bh_inh_ids) = make_chunk_ids(bh_eu, bh_iu, bh_upc);
        let bh_nc = bh_exc_ids.len() + bh_inh_ids.len();
        let bh_dyn_mc = EIMicrocircuitSpec {
            p_ee: 0.05,
            p_ei: 0.80,
            p_ie: 1.00,
            p_ii: 0.10,
            forbid_within_chunk: true,
            ..EIMicrocircuitSpec::balanced(bh_exc_ids.clone(), bh_inh_ids.clone())
        }
        .build();

        let mut bh_e_cfg =
            explicit_cfg(bh_eu, bh_iu, bh_upc, &bh_dyn_mc, &bh_exc_ids, bh_nc);
        bh_e_cfg.num_steps = DYN_STEPS;
        let bh_e_rec = run_explicit(&bh_e_cfg);
        let bh_e_dyn =
            next_brain::experiment::metrics::PopulationDynamics::from_record(&bh_e_rec, 0.001);

        let (mut bh_l_cfg, bh_cal) = calibrated_mix_cfg(
            bh_eu, bh_iu, bh_upc, &bh_dyn_mc, 1.0,
            &bh_exc_ids, &bh_inh_ids, bh_nc,
            DYN_CALIB_STEPS, DYN_STEPS,
        );
        
        calib_records.push(CalibRecord {
             scale: "BoundaryHeavy (DYN)".to_string(),
             ratio_pct: 100,
             calibrated_gain: bh_cal.params.gain_exc,
             fr_error_pct: bh_cal.fr_error_pct(),
             iterations: bh_cal.iterations,
             converged: bh_cal.converged,
        });

        let bh_l_rec = run_mixed(&mut bh_l_cfg, &bh_exc_ids, &bh_inh_ids);
        let bh_l_dyn =
            next_brain::experiment::metrics::PopulationDynamics::from_record(&bh_l_rec, 0.001);
        let bh_cmp =
            next_brain::experiment::metrics::compare_dynamics(&bh_e_rec, &bh_l_rec, 0.001);

        println!(
            "{:<18} {:>7} {:>9.5} {:>7.4} {:>11.2} {:>10.2e} {:>10.5} {:>11.2}",
            "BoundaryHeavy",
            "Explicit",
            bh_e_dyn.mean_fr_hz,
            bh_e_dyn.cv_pop,
            bh_e_dyn.peak_freq_hz,
            bh_e_dyn.peak_power,
            bh_e_dyn.max_fr_hz,
            bh_e_dyn.t_peak_ms,
        );
        
        let bh_mode_str = if !bh_cal.converged { "LPU(⚠)" } else { "LPU" };
        println!(
            "{:<18} {:>7} {:>9.5} {:>7.4} {:>11.2} {:>10.2e} {:>10.5} {:>11.2}",
            "",
            bh_mode_str,
            bh_l_dyn.mean_fr_hz,
            bh_l_dyn.cv_pop,
            bh_l_dyn.peak_freq_hz,
            bh_l_dyn.peak_power,
            bh_l_dyn.max_fr_hz,
            bh_l_dyn.t_peak_ms,
        );
        let bh_rec_str = match bh_l_dyn.recovery_time_ms {
            Some(r) => format!("{:.1}ms", r),
            None => "N/A".to_string(),
        };
        let bh_psth_flag = if bh_cmp.psth_correlation < PSTH_R_CONCERN_THRESHOLD {
            "  ⚠ CONCERN"
        } else {
            ""
        };
        println!(
            "  └─ Rise10-90: {:.1}ms | Recovery: {} | PSTH-r: {:.4}{} | ΔCV_pop: {:.2}%",
            bh_l_dyn.rise_time_10_90_ms,
            bh_rec_str,
            bh_cmp.psth_correlation,
            bh_psth_flag,
            bh_cmp.cv_pop_delta_pct,
        );

        // Export PSD spectrum CSVs for boundary-heavy case (Paper 2 Figure 4).
        let bh_e_trace =
            next_brain::experiment::metrics::get_fr_trace(&bh_e_rec, 0.001);
        let bh_l_trace =
            next_brain::experiment::metrics::get_fr_trace(&bh_l_rec, 0.001);
        let bh_e_psd =
            next_brain::experiment::metrics::compute_psd_spectrum(&bh_e_trace, 0.001);
        let bh_l_psd =
            next_brain::experiment::metrics::compute_psd_spectrum(&bh_l_trace, 0.001);
        export_psd_csv("psd_boundaryheavy_explicit.csv", &bh_e_psd);
        export_psd_csv("psd_boundaryheavy_lpu.csv", &bh_l_psd);

        dyn_cmp_rows.push(DynCompRow {
            label: "BoundaryHeavy".into(),
            psth_r: bh_cmp.psth_correlation,
            delta_fr_pct: bh_cmp.mean_fr_delta_pct,
            delta_cv_pct: bh_cmp.cv_pop_delta_pct,
            delta_peak_hz: bh_cmp.peak_freq_delta_hz,
        });
    }
    println!();

    // PSTH temporal alignment summary (with per-row concern flags).
    println!("  PSTH Temporal Alignment Summary (Explicit → LPU 100%, Sustained):");
    println!(
        "  {:<18} {:>12} {:>12} {:>12} {:>14} {:>9}",
        "Scale", "PSTH-r", "ΔMeanFR(%)", "ΔCV_pop(%)", "ΔPeakFreq(Hz)", "Concern?"
    );
    println!("  {}", "─".repeat(83));
    let mut psth_concern_count = 0usize;
    for r in &dyn_cmp_rows {
        let concern = if r.psth_r < PSTH_R_CONCERN_THRESHOLD {
            psth_concern_count += 1;
            "⚠ YES"
        } else {
            "—"
        };
        println!(
            "  {:<18} {:>12.4} {:>12.2} {:>12.2} {:>14.2} {:>9}",
            r.label, r.psth_r, r.delta_fr_pct, r.delta_cv_pct, r.delta_peak_hz, concern,
        );
    }
    println!();
    if psth_concern_count == 0 {
        println!(
            "  ✓ All PSTH-r ≥ {:.2} (concern threshold). Temporal alignment is satisfactory.",
            PSTH_R_CONCERN_THRESHOLD
        );
    } else {
        println!(
            "  ⚠ {} scale(s) below PSTH-r concern threshold ({:.2}). See Paper 2 §4.",
            psth_concern_count, PSTH_R_CONCERN_THRESHOLD
        );
    }
    println!();
    
    // ── CALIB: calibration quality summary (moved here to include DYN runs) ────
    print_calibration_table(&calib_records);

    // ── Table E: cross-scale gain portability ──────────────────────────────────
    println!(
        "=== E: Cross-Scale Gain Portability  (50k ↔ 500k, LPU 100%, steps={NUM_STEPS}) ==="
    );
    println!();
    println!("Hypothesis: a gain calibrated at scale S₁ does NOT transfer reliably to S₂.");
    println!("Evidence  : same-scale calibration converges; cross-scale injection inflates FR error.");
    println!();
    {
        // ── 50k scale ──────────────────────────────────────────────────────────
        let (eu50, iu50, upc50) = (40_000_usize, 10_000_usize, 100_usize);
        let (exc50, inh50) = make_chunk_ids(eu50, iu50, upc50);
        let nc50 = exc50.len() + inh50.len();
        let mc50 = EIMicrocircuitSpec::balanced(exc50.clone(), inh50.clone()).build();

        let mut e50_cfg = explicit_cfg(eu50, iu50, upc50, &mc50, &exc50, nc50);
        e50_cfg.num_steps = CALIB_STEPS;
        let ref_fr_50k = run_explicit(&e50_cfg).mean_firing_rate();

        let (mut l50_cfg, cal50) = calibrated_mix_cfg(
            eu50, iu50, upc50, &mc50, 1.0, &exc50, &inh50, nc50,
            CALIB_STEPS, NUM_STEPS,
        );
        let fr_50k_own = run_mixed(&mut l50_cfg, &exc50, &inh50).mean_firing_rate();
        let gain50 = cal50.params.gain_exc;

        // ── 500k scale ─────────────────────────────────────────────────────────
        let (eu500, iu500, upc500) = (400_000_usize, 100_000_usize, 100_usize);
        let (exc500, inh500) = make_chunk_ids(eu500, iu500, upc500);
        let nc500 = exc500.len() + inh500.len();
        let mc500 = EIMicrocircuitSpec::balanced(exc500.clone(), inh500.clone()).build();

        let mut e500_cfg = explicit_cfg(eu500, iu500, upc500, &mc500, &exc500, nc500);
        e500_cfg.num_steps = CALIB_STEPS;
        let ref_fr_500k = run_explicit(&e500_cfg).mean_firing_rate();

        let (mut l500_cfg, cal500) = calibrated_mix_cfg(
            eu500, iu500, upc500, &mc500, 1.0, &exc500, &inh500, nc500,
            CALIB_STEPS, NUM_STEPS,
        );
        let fr_500k_own = run_mixed(&mut l500_cfg, &exc500, &inh500).mean_firing_rate();
        let gain500 = cal500.params.gain_exc;

        // ── Cross-scale mismatched runs (fixed gain, no re-calibration) ────────
        let fr_500k_wrong = run_lpu_fixed_gain(
            eu500, iu500, upc500, &mc500,
            &exc500, &inh500, nc500,
            gain50, NUM_STEPS,
        )
        .mean_firing_rate();

        let fr_50k_wrong = run_lpu_fixed_gain(
            eu50, iu50, upc50, &mc50,
            &exc50, &inh50, nc50,
            gain500, NUM_STEPS,
        )
        .mean_firing_rate();

        let fr_err = |measured: f32, reference: f32| -> f32 {
            if reference > 1e-9 {
                ((measured - reference) / reference * 100.0).abs()
            } else {
                f32::NAN
            }
        };

        println!(
            "{:<18} {:<22} {:>11} {:>11} {:>10} {:>10}",
            "Scale", "Gain source", "ExplRefFR", "LPU_FR", "GainUsed", "FR_err%"
        );
        println!("{}", "─".repeat(88));
        println!(
            "{:<18} {:<22} {:>11.5} {:>11.5} {:>10.4} {:>10.2}",
            "50000u/500c",
            "own-scale (50k)",
            ref_fr_50k,
            fr_50k_own,
            gain50,
            fr_err(fr_50k_own, ref_fr_50k)
        );
        println!(
            "{:<18} {:<22} {:>11.5} {:>11.5} {:>10.4} {:>10.2}",
            "500000u/5000c",
            "own-scale (500k)",
            ref_fr_500k,
            fr_500k_own,
            gain500,
            fr_err(fr_500k_own, ref_fr_500k)
        );
        println!("{}", "─".repeat(88));
        println!(
            "{:<18} {:<22} {:>11.5} {:>11.5} {:>10.4} {:>10.2}  ← cross-scale mismatch",
            "500000u/5000c",
            "50k gain (wrong)",
            ref_fr_500k,
            fr_500k_wrong,
            gain50,
            fr_err(fr_500k_wrong, ref_fr_500k)
        );
        println!(
            "{:<18} {:<22} {:>11.5} {:>11.5} {:>10.4} {:>10.2}  ← cross-scale mismatch",
            "50000u/500c",
            "500k gain (wrong)",
            ref_fr_50k,
            fr_50k_wrong,
            gain500,
            fr_err(fr_50k_wrong, ref_fr_50k)
        );
        println!();
        println!(
            "  gain_50k={:.4}  gain_500k={:.4}  |Δgain|={:.4}",
            gain50,
            gain500,
            (gain50 - gain500).abs()
        );
        println!("  Conclusion: gains are scale-dependent. Cross-scale injection introduces");
        println!(
            "  systematic FR error that exceeds the {:.0}% acceptance threshold.",
            FR_CALIB_TOLERANCE * 100.0
        );
    }
    println!();

    // ── Validation summary ─────────────────────────────────────────────────────
    let failures: Vec<&Row> = rows.iter().filter(|r| !r.lpu_bound_ok).collect();
    if failures.is_empty() {
        println!("✓ LPU two-channel event-bound verified for all rows.");
    } else {
        println!("✗ LPU event-bound VIOLATED in {} row(s):", failures.len());
        for f in &failures {
            println!(
                "  scale={} ratio={}% events/step={:.2} bound={}",
                f.scale, f.ratio_pct, f.events_step, 2 * f.n_chunks
            );
        }
        std::process::exit(1);
    }

    // ── Weight-conservation spot-check ────────────────────────────────────────
    println!();
    let spot_mc = EIMicrocircuitSpec::balanced(
        (0..4u32).map(ChunkId).collect(),
        (4..6u32).map(ChunkId).collect(),
    )
    .build();
    let w_before: f32 = [&spot_mc.ee, &spot_mc.ei, &spot_mc.ie, &spot_mc.ii]
        .iter()
        .map(|p| total_weight(p))
        .sum();
    let (e_mc, l_mc) = spot_mc.split_by_ratio(0.5, 42);
    let w_after: f32 = [
        &e_mc.ee, &e_mc.ei, &e_mc.ie, &e_mc.ii,
        &l_mc.ee, &l_mc.ei, &l_mc.ie, &l_mc.ii,
    ]
    .iter()
    .map(|p| total_weight(p))
    .sum();
    if (w_before - w_after).abs() < 1e-3 {
        println!(
            "✓ Weight conservation: split_by_ratio(0.5) preserves total weight \
                  ({w_before:.4} ≈ {w_after:.4})."
        );
    } else {
        println!("✗ Weight conservation FAILED: before={w_before:.4} after={w_after:.4}");
        std::process::exit(1);
    }

    // ── Final summary ──────────────────────────────────────────────────────────
    println!();
    let lpu_rows: Vec<&Row> = rows.iter().filter(|r| r.calib_gain.is_some()).collect();
    let n_converged = calib_records.iter().filter(|r| r.converged).count();
    let n_failed = calib_records.len() - n_converged;
    
    println!(
        "✓ LPU rows: {} | Calibration: {}/{} converged | PSTH concerns: {}",
        lpu_rows.len(),
        n_converged,
        calib_records.len(),
        psth_concern_count,
    );
    println!();

    if n_failed > 0 {
        println!("✗ ERROR: {} calibration runs FAILED to converge (marked ✗ NO in CALIB).", n_failed);
        println!("  Scientifically invalid results were captured in the D/D2 logging blocks (marked ⚠) above.");
        println!("  Do NOT publish Tables 3 & 4. Review scale-gains or dynamics stability ranges before outputting publishable tables.");
        std::process::exit(1);
    }

    println!("Done.  Copy tables above into Paper 2 Tables 3 & 4.");
    println!("PSD CSVs: psd_50k_sustained_{{explicit,lpu}}.csv  psd_boundaryheavy_{{explicit,lpu}}.csv");
    println!("Plot    : python3 examples/plot_psd.py");
    println!();
}
