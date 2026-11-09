//! Additive E3 endpoint experiment. No historical test or production code is edited.
//! Compile with --cfg raw_sum_ablation only against the separately patched library.
use std::{fs::File, io::Write, path::PathBuf};
use next_brain::connectivity::{event_router::EventRouter, microcircuit::EIMicrocircuitSpec};
use next_brain::core::chunk::ChunkId;
use next_brain::experiment::{
    harness::{HarnessConfig, RunRecord, run_explicit, run_mixed_with_retention},
    input_protocol::{DriveType, InputProtocol, OperatingRegime},
    metrics::compare_dynamics,
    retention::{MotifClass, RetentionPolicy},
};
use next_brain::lpu::{aggregator::AggregatorParams, proxy::ProxyMode, proxy_params::RicherProxyParams};

const DT_MS: f32 = 0.1;
const DT_S: f32 = DT_MS / 1000.0;
const UNITS: usize = 12_500;
const STEPS: usize = 200;

fn config(exc_ids: &[ChunkId], mode: ProxyMode, params: RicherProxyParams) -> HarnessConfig {
    let input_protocol = InputProtocol::for_regime(OperatingRegime::Sustained, exc_ids.to_vec());
    assert!(matches!(input_protocol.drive, DriveType::Tonic { strength: 10.0 }));
    assert_eq!(input_protocol.delay_slots, 0);
    HarnessConfig {
        exc_units: 10_000, inh_units: 2_500, units_per_chunk: 100,
        dt: DT_MS, num_steps: STEPS as u64, input_protocol, router: None,
        lpu_params: AggregatorParams::default(), replaced_circuit: None, lpu_index: None,
        proxy_mode: mode, richer_params: params,
    }
}

fn spikes(record: &RunRecord) -> u64 {
    record.steps.iter().map(|s| s.total_spikes as u64).sum()
}

#[test]
fn e3_zero_and_bridge() {
    let output = PathBuf::from(std::env::var("E3_OUTPUT_DIR").expect("E3_OUTPUT_DIR required"));
    let exc_ids: Vec<_> = (0..100).map(ChunkId).collect();
    let inh_ids: Vec<_> = (100..125).map(ChunkId).collect();
    let spec = EIMicrocircuitSpec::boundary_heavy_hetero(exc_ids.clone(), inh_ids.clone());
    assert_eq!(spec.rng_seed, 200);
    assert_eq!(spec.weight_spread, 0.5);
    assert_eq!(spec.delay_slots, 1);
    assert!(spec.forbid_within_chunk);
    assert_eq!((spec.p_ee, spec.p_ei, spec.p_ie, spec.p_ii), (0.15, 0.25, 0.25, 0.20));
    assert_eq!((spec.w_ee, spec.w_ei, spec.w_ie, spec.w_ii), (0.6, 0.8, 1.4, 0.5));
    let mc = spec.build();
    let mut explicit_cfg = config(&exc_ids, ProxyMode::FourChannel, RicherProxyParams::default());
    explicit_cfg.router = Some(EventRouter::from_projections(&mc.all_proj_refs(), 125));
    let explicit = run_explicit(&explicit_cfg);
    assert_eq!(explicit.steps.len(), STEPS);
    assert_eq!(explicit.total_units, UNITS);
    assert_eq!(explicit.total_events(), 32_247, "Existing E3 reference event count");
    assert_eq!(spikes(&explicit), 124_500, "Existing E3 reference spike count");
    let reference_events = explicit.total_events();
    let reference_spikes = spikes(&explicit);
    let stateful_params = RicherProxyParams { gain_fast_exc: 2.5, gain_fast_inh: 0.4, ..Default::default() };
    let variants = if cfg!(raw_sum_ablation) {
        vec![("raw_sum", ProxyMode::Stateful, stateful_params)]
    } else {
        vec![
            ("filtered_4ch", ProxyMode::FourChannel, RicherProxyParams::default()),
            ("original_instrumented", ProxyMode::Stateful, stateful_params),
        ]
    };
    let build_label = if cfg!(raw_sum_ablation) { "raw_sum" } else { "original" };
    let mut results = File::create(output.join(format!("{build_label}-records.csv"))).unwrap();
    writeln!(results, "variant,label,benchmark,units,steps,dt_ms,retention_policy,threshold,retained_edges,total_edges,retained_edges_pct,psth_r,fr_delta,explicit_events,approx_events,event_ratio_from_counts,explicit_spikes,approx_spikes,mismatched_slots,max_step_spike_delta,mixed_explicit_events,proxy_events,gain_fast_exc,gain_fast_inh,psth_r_f32_bits,fr_delta_f32_bits,slot_file").unwrap();
    for (variant, mode, params) in variants {
        let cfg = config(&exc_ids, mode, params.clone());
        for zero in [true, false] {
            // Empty classes keep exactly zero edges, without relying on a weight bound.
            // The existing harness supplies an empty explicit router in this case.
            let policy = RetentionPolicy::new(
                if zero { vec![] } else { vec![MotifClass::StrongInhibitoryLoop] }, 2.0,
            );
            let result = run_mixed_with_retention(&cfg, &mc, &policy, &exc_ids, &inh_ids);
            let approx = &result.record;
            assert_eq!(approx.steps.len(), STEPS);
            assert_eq!(approx.total_units, UNITS);
            assert_eq!(result.stats.total_edges, result.stats.kept_explicit + result.stats.replaced_proxy);
            assert_eq!(approx.total_events(), result.explicit_events + result.proxy_events);
            if zero {
                assert_eq!(result.stats.kept_explicit, 0);
                assert_eq!(result.stats.replaced_proxy, result.stats.total_edges);
                assert_eq!(result.explicit_events, 0);
            } else {
                assert!(result.stats.kept_explicit > 0);
            }
            let cmp = compare_dynamics(&explicit, approx, DT_S);
            assert!(cmp.psth_correlation.is_finite() && cmp.mean_fr_delta_pct.is_finite());
            let mismatches = explicit.steps.iter().zip(&approx.steps).filter(|(a,b)| a.total_spikes != b.total_spikes).count();
            let max_delta = explicit.steps.iter().zip(&approx.steps).map(|(a,b)| a.total_spikes.abs_diff(b.total_spikes)).max().unwrap();
            let label = if zero { "zero_retention" } else { "bridge_thr=2.00(~2%)" };
            let slot_file = format!("slots/{variant}-{}.csv", if zero { "zero" } else { "bridge" });
            let mut slots = File::create(output.join(&slot_file)).unwrap();
            writeln!(slots, "slot,explicit_spikes,approx_spikes,explicit_events,approx_events").unwrap();
            for (a,b) in explicit.steps.iter().zip(&approx.steps) {
                assert_eq!(a.slot, b.slot);
                writeln!(slots, "{},{},{},{},{}", a.slot, a.total_spikes, b.total_spikes, a.events_injected, b.events_injected).unwrap();
            }
            writeln!(results, "{variant},{label},E3 heterogeneous,{UNITS},{STEPS},0.1,{},{},{},{},{:.17},{:.17},{:.17},{},{},{:.17},{},{},{},{},{},{},{:.17},{:.17},{},{},{}",
                if zero { "empty" } else { "StrongInhibitoryLoop" }, if zero { "" } else { "2.0" },
                result.stats.kept_explicit, result.stats.total_edges,
                100.0 * result.stats.kept_explicit as f64 / result.stats.total_edges as f64,
                cmp.psth_correlation as f64, cmp.mean_fr_delta_pct as f64,
                reference_events, approx.total_events(), approx.total_events() as f64 / reference_events as f64,
                reference_spikes, spikes(approx), mismatches, max_delta,
                result.explicit_events, result.proxy_events,
                params.gain_fast_exc as f64, params.gain_fast_inh as f64,
                cmp.psth_correlation.to_bits(), cmp.mean_fr_delta_pct.to_bits(), slot_file,
            ).unwrap();
            println!("E3ZERO {variant} {label}: kept={}/{} r={:.9} fr_delta={:.9}% Q={:.12} events={}/{} spikes={}/{} mismatches={}",
                result.stats.kept_explicit, result.stats.total_edges, cmp.psth_correlation,
                cmp.mean_fr_delta_pct, approx.total_events() as f64 / reference_events as f64,
                approx.total_events(), reference_events, spikes(approx), reference_spikes, mismatches);
        }
    }
}
