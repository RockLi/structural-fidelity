use next_brain::connectivity::event_router::EventRouter;
use next_brain::connectivity::microcircuit::EIMicrocircuitSpec;
use next_brain::experiment::frontier::{FrontierPoint, FrontierReport};
use next_brain::experiment::harness::{HarnessConfig, run_explicit, run_lpu};
use next_brain::experiment::input_protocol::{InputProtocol, OperatingRegime};
use next_brain::experiment::lpu_index::LpuTopologyIndex;
use next_brain::lpu::aggregator::AggregatorParams;
use next_brain::lpu::proxy::ProxyMode;
use next_brain::lpu::proxy_params::RicherProxyParams;

const DT_MS: f32 = 0.1;
const DT_S: f32 = DT_MS / 1000.0;
const UNITS_PER_CHUNK: usize = 100;

fn make_ei_chunks(n_exc: usize, n_inh: usize) -> (Vec<next_brain::core::chunk::ChunkId>, Vec<next_brain::core::chunk::ChunkId>) {
    let exc_ids: Vec<next_brain::core::chunk::ChunkId> = (0..n_exc as u32).map(next_brain::core::chunk::ChunkId).collect();
    let inh_ids: Vec<next_brain::core::chunk::ChunkId> = (n_exc as u32..(n_exc + n_inh) as u32).map(next_brain::core::chunk::ChunkId).collect();
    (exc_ids, inh_ids)
}

fn main() {
    let mut args = std::env::args().skip(1);
    let mut bench_name = String::new();
    let mut out_file = String::new();

    while let Some(arg) = args.next() {
        if arg == "--bench" {
            bench_name = args.next().unwrap();
        } else if arg == "--out" {
            out_file = args.next().unwrap();
        }
    }

    if bench_name.is_empty() {
        bench_name = "e1".to_string();
    }

    let report = match bench_name.as_str() {
        "e1" => run_e1_sweep(),
        "e3" => run_e3_sweep(),
        _ => panic!("Unknown bench: {}", bench_name),
    };

    println!("{}", report.markdown_table());
    println!("{}", report.summary_table());

    if let Some(best) = report.best_by_fidelity() {
        println!("Best by fidelity:\n  {}\n  psth_r={:.3} fr_delta={:+.1}% spike_ratio={:.3}", 
                 best.label, best.psth_correlation, best.mean_fr_delta_pct, best.spike_ratio);
    }

    if !out_file.is_empty() {
        report.write_csv(std::path::Path::new(&out_file)).unwrap();
        println!("CSV written to: {}", out_file);
    }
}

fn run_e1_sweep() -> FrontierReport {
    let (exc_ids, inh_ids) = make_ei_chunks(400, 100);
    sweep_calibration(
        "E1 50k Sustained",
        40_000, 10_000,
        500, // steps = 50ms at dt=0.1
        OperatingRegime::Sustained,
        EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()),
        exc_ids, inh_ids,
    )
}

fn run_e3_sweep() -> FrontierReport {
    let (exc_ids, inh_ids) = make_ei_chunks(100, 25);
    let spec = EIMicrocircuitSpec {
        p_ee: 0.05,
        p_ei: 0.80,
        p_ie: 1.00,
        p_ii: 0.10,
        forbid_within_chunk: true, // Boundary-heavy
        ..EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone())
    };
    sweep_calibration(
        "E3 Boundary-Heavy",
        10_000, 2_500,
        300, 
        OperatingRegime::Sustained,
        spec,
        exc_ids, inh_ids,
    )
}

fn build_baseline_cfg(
    exc_units: usize, inh_units: usize, num_steps: u64, regime: OperatingRegime,
    mc: next_brain::connectivity::microcircuit::EIMicrocircuit,
    exc_ids: &[next_brain::core::chunk::ChunkId], total_chunks: usize,
) -> HarnessConfig {
    let projs = mc.all_proj_refs();
    let router = EventRouter::from_projections(&projs, total_chunks);
    HarnessConfig {
        exc_units, inh_units,
        units_per_chunk: UNITS_PER_CHUNK,
        dt: DT_MS,
        num_steps,
        input_protocol: InputProtocol::for_regime(regime, exc_ids.to_vec()),
        router: Some(router),
        lpu_params: AggregatorParams::default(),
        replaced_circuit: None,
        lpu_index: None,
        proxy_mode: ProxyMode::FourChannel,
        richer_params: RicherProxyParams::default(),
    }
}

fn sweep_calibration(
    benchmark_name: &str,
    exc_units: usize, inh_units: usize,
    num_steps: u64,
    regime: OperatingRegime,
    spec: EIMicrocircuitSpec,
    exc_ids: Vec<next_brain::core::chunk::ChunkId>, 
    inh_ids: Vec<next_brain::core::chunk::ChunkId>,
) -> FrontierReport {
    let mut report = FrontierReport::new(benchmark_name);
    let total_chunks = exc_ids.len() + inh_ids.len();

    println!("Running explicit baseline...");
    let mc_expl = spec.build();
    let cfg_expl = build_baseline_cfg(exc_units, inh_units, num_steps, regime, mc_expl, &exc_ids, total_chunks);
    let rec_exp = run_explicit(&cfg_expl);

    println!("Running 2ch-default...");
    let mc_2ch = spec.build();
    let idx_2ch = LpuTopologyIndex::build_with_mode(&mc_2ch, total_chunks, ProxyMode::TwoChannel);
    let mut cfg_2ch = HarnessConfig {
        router: None,
        replaced_circuit: Some(mc_2ch),
        lpu_index: Some(idx_2ch),
        proxy_mode: ProxyMode::TwoChannel,
        ..build_baseline_cfg(exc_units, inh_units, num_steps, regime, spec.build(), &exc_ids, total_chunks)
    };
    let rec_2ch = run_lpu(&mut cfg_2ch, &exc_ids, &inh_ids);
    report.add(FrontierPoint::from_runs("2ch-default", &rec_exp, &rec_2ch, DT_S));

    println!("Running 4ch-default...");
    let mc_4ch = spec.build();
    let idx_4ch = LpuTopologyIndex::build_with_mode(&mc_4ch, total_chunks, ProxyMode::FourChannel);
    let mut cfg_4ch = HarnessConfig {
        router: None,
        replaced_circuit: Some(mc_4ch),
        lpu_index: Some(idx_4ch),
        proxy_mode: ProxyMode::FourChannel,
        ..build_baseline_cfg(exc_units, inh_units, num_steps, regime, spec.build(), &exc_ids, total_chunks)
    };
    let rec_4ch = run_lpu(&mut cfg_4ch, &exc_ids, &inh_ids);
    report.add(FrontierPoint::from_runs("4ch-default", &rec_exp, &rec_4ch, DT_S));

    let gains = vec![0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0];
    let taus = vec![1.0, 3.0, 5.0];

    for &tau in &taus {
        for &gain in &gains {
            let label = format!("4ch-g{:.1}-t{:.1}", gain, tau);
            println!("Running {}...", label);
            
            let mc_sweep = spec.build();
            let idx_sweep = LpuTopologyIndex::build_with_mode(&mc_sweep, total_chunks, ProxyMode::FourChannel);
            let mut cfg_sweep = HarnessConfig {
                router: None,
                replaced_circuit: Some(mc_sweep),
                lpu_index: Some(idx_sweep),
                proxy_mode: ProxyMode::FourChannel,
                richer_params: RicherProxyParams {
                    gain_fast_exc: gain,
                    tau_fast_exc: tau,
                    ..RicherProxyParams::default()
                },
                ..build_baseline_cfg(exc_units, inh_units, num_steps, regime, spec.build(), &exc_ids, total_chunks)
            };
            
            let rec_sweep = run_lpu(&mut cfg_sweep, &exc_ids, &inh_ids);
            report.add(FrontierPoint::from_runs(&label, &rec_exp, &rec_sweep, DT_S));
        }
    }

    report
}
