//! Phase 2 integration tests: LPU vs. explicit comparison.
//!
//! Validates Tasks 2, 2.5, 3, 4, 5 — that:
//! (a) LPU mode produces non-zero activity under a driven protocol.
//! (b) DynamicsFidelity computes meaningful metrics from paired runs.
//! (c) The harness RecordRun struct correctly accounts resources.
//! (d) Calibrator converges on a trivial test case.

#[cfg(test)]
mod phase2_lpu {
    use next_brain::connectivity::{event_router::EventRouter, microcircuit::EIMicrocircuitSpec};
    use next_brain::core::chunk::ChunkId;
    use next_brain::experiment::{
        harness::{HarnessConfig, run_explicit},
        input_protocol::InputProtocol,
    };
    use next_brain::lpu::{
        aggregator::{AggregationMode, AggregatorParams, compute_lpu_drive},
        calibration::{CalibrationProbe, calibrate},
        kernel::{lpu_resource_delta, step_lpu_euler},
    };
    use next_brain::metrics::{dynamics::DynamicsFidelity, resource::ResourceComparison};

    // ── Test 1: LPU kernel step does not panic ──────────────────────────────────
    #[test]
    fn test_lpu_kernel_step_no_panic() {
        use next_brain::state::ChunkStateArrays;
        let mut state = ChunkStateArrays::new(100);
        let params = AggregatorParams::default();
        step_lpu_euler(&mut state, 2.0, 0.5, 0.001, 0, &params);
        // Voltages should be non-zero after a step with drive.
        let any_nonzero = state.voltages.iter().any(|&v| v != -65.0);
        assert!(any_nonzero, "LPU kernel must update voltages");
    }

    // ── Test 2: compute_lpu_drive produces expected channel split ───────────────
    #[test]
    fn test_compute_lpu_drive_excitatory() {
        let params = AggregatorParams {
            mode: AggregationMode::NormalizedRate,
            gain_exc: 2.0,
            gain_inh: 1.0,
            tau_field: 10.0,
        };
        // 10 spikes from 100 units → rate = 0.1 → exc_drive = 0.1 × 2.0 = 0.2
        let (exc, inh) = compute_lpu_drive(10.0, 100, 0.0, 0.0, 0.001, &params, true);
        assert!((exc - 0.2).abs() < 1e-5, "exc_drive = {}", exc);
        assert!(
            (inh).abs() < 1e-6,
            "inh_drive should be 0 for excitatory src"
        );
    }

    #[test]
    fn test_compute_lpu_drive_inhibitory() {
        let params = AggregatorParams {
            mode: AggregationMode::NormalizedRate,
            gain_exc: 1.0,
            gain_inh: 3.0,
            tau_field: 10.0,
        };
        // 5 spikes from 50 units → rate = 0.1 → inh_drive = 0.1 × 3.0 = 0.3
        let (exc, inh) = compute_lpu_drive(5.0, 50, 0.0, 0.0, 0.001, &params, false);
        assert!(
            (exc).abs() < 1e-6,
            "exc_drive should be 0 for inhibitory src"
        );
        assert!((inh - 0.3).abs() < 1e-5, "inh_drive = {}", inh);
    }

    // ── Test 3: lpu_resource_delta computes savings correctly ───────────────────
    #[test]
    fn test_lpu_resource_delta() {
        let (saved, bytes) = lpu_resource_delta(100, 24);
        assert_eq!(saved, 99); // 100 explicit events - 1 broadcast = 99 saved
        assert_eq!(bytes, 99 * 24);
    }

    // ── Test 4: DynamicsFidelity on matched runs returns unit correlation ───────
    #[test]
    fn test_dynamics_fidelity_identical_runs() {
        use next_brain::experiment::harness::RunRecord;
        use next_brain::experiment::harness::StepRecord;

        // Create two identical run records.
        let record = RunRecord {
            mode: None,
            total_units: 100,
            num_chunks: 1,
            steps: vec![
                StepRecord {
                    slot: 0,
                    total_spikes: 10,
                    active_chunks: 1,
                    dormant_skips: 0,
                    events_injected: 5,
                },
                StepRecord {
                    slot: 1,
                    total_spikes: 15,
                    active_chunks: 1,
                    dormant_skips: 0,
                    events_injected: 5,
                },
                StepRecord {
                    slot: 2,
                    total_spikes: 5,
                    active_chunks: 1,
                    dormant_skips: 0,
                    events_injected: 5,
                },
            ],
        };

        let fidelity = DynamicsFidelity::compute(&record, &record, 1.0);
        // Identical runs must have 0 deviation and correlation 1.0 (or NaN if std=0).
        assert!(
            fidelity.firing_rate_deviation.abs() < 1e-5,
            "identical runs must have 0 rate deviation"
        );
        // Correlation is 1.0 when trajectories are identical and have variance.
        assert!(
            (fidelity.trajectory_correlation - 1.0).abs() < 1e-4
                || fidelity.trajectory_correlation.is_nan(),
            "identical trajectories must correlate at 1.0"
        );
    }

    // ── Test 5: Calibrator converges for a trivial case ─────────────────────────
    #[test]
    fn test_calibrator_trivial_convergence() {
        // Explicit baseline: 0.05 mean firing rate.
        let explicit_probe = CalibrationProbe {
            mean_firing_rate: 0.05,
            mean_g_exc: 0.5,
            mean_g_inh: 0.0,
        };

        // LPU probe function: returns the rate proportional to gain_exc.
        // At gain_exc=1.0 → returns 0.05 → should converge immediately.
        let lpu_probe_fn = |params: &AggregatorParams| CalibrationProbe {
            mean_firing_rate: 0.05 * params.gain_exc,
            mean_g_exc: 0.5 * params.gain_exc,
            mean_g_inh: 0.0,
        };

        let result = calibrate(
            &explicit_probe,
            lpu_probe_fn,
            AggregationMode::NormalizedRate,
            0.05,
            50,
        );

        assert!(
            result.converged,
            "calibration must converge for a linear probe"
        );
        assert!(result.firing_rate_error.abs() < 0.05 * 0.05 + 1e-4);
        println!("{}", result.summary());
    }

    // ── Test 6: Harness run_explicit produces spikes under strong stimulus ──────
    #[test]
    fn test_harness_explicit_produces_spikes() {
        use next_brain::experiment::input_protocol::DriveType;

        let exc_ids: Vec<ChunkId> = (0..4).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6).map(ChunkId).collect();

        let mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();
        let projs = vec![&mc.ee, &mc.ei, &mc.ie, &mc.ii];
        let router = EventRouter::from_projections(&projs, 6);

        // Use large dt (0.1 ms) so Euler integration reaches threshold quickly.
        // With dt=0.1: dV ≈ (-(-65) + 40) * 0.1 = 10.5 per step → threshold in ~10 steps.
        let protocol = InputProtocol {
            target_chunks: exc_ids.clone(),
            drive: DriveType::Tonic { strength: 40.0 },
            delay_slots: 0,
        };

        let config = HarnessConfig {
            exc_units: 400,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            num_steps: 50,
            input_protocol: protocol,
            router: Some(router),
            lpu_params: AggregatorParams::default(),
            replaced_circuit: None,
            lpu_index: None,
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
        };

        let record = run_explicit(&config);
        let total_spikes: u32 = record.steps.iter().map(|s| s.total_spikes).sum();
        assert!(
            total_spikes > 0,
            "explicit run with strong drive must produce spikes"
        );
        println!("Explicit run: mean_rate={:.4}", record.mean_firing_rate());
    }

    // ── Test 7: ResourceComparison.summary() doesn't panic ─────────────────────
    #[test]
    fn test_resource_comparison_summary() {
        use next_brain::experiment::harness::{RunRecord, StepRecord};

        let make_record = |events: u32| RunRecord {
            mode: None,
            total_units: 100,
            num_chunks: 4,
            steps: vec![
                StepRecord {
                    slot: 0,
                    total_spikes: 5,
                    active_chunks: 2,
                    dormant_skips: 2,
                    events_injected: events,
                },
                StepRecord {
                    slot: 1,
                    total_spikes: 3,
                    active_chunks: 2,
                    dormant_skips: 2,
                    events_injected: events,
                },
            ],
        };

        let explicit_record = make_record(40);
        let lpu_record = make_record(4);

        let exc_ids: Vec<ChunkId> = (0..4).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6).map(ChunkId).collect();
        let mc = EIMicrocircuitSpec::balanced(exc_ids, inh_ids).build();

        let comp = ResourceComparison::compute(&explicit_record, &lpu_record, &mc);
        let s = comp.summary();
        assert!(!s.is_empty());
        println!("{}", s);
    }

    // ── Test 9: run_lpu() end-to-end with a real replaced circuit ───────────────
    //
    // This test exercises the full LPU path: EIMicrocircuit topology, proxy event
    // injection, dormant-chunk wake-up, and spike recording. Previously this path
    // was never called from the test suite, so regressions in topology propagation
    // or event accounting would not trip CI.
    #[test]
    fn test_run_lpu_end_to_end() {
        use next_brain::experiment::{
            harness::{HarnessConfig, run_lpu},
            input_protocol::{InputProtocol, OperatingRegime},
        };

        let exc_ids: Vec<ChunkId> = (0..4).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6).map(ChunkId).collect();

        let mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();
        let mc2 = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();

        let config = HarnessConfig {
            exc_units: 400,
            // 200 inh units / 100 per chunk = 2 inh chunks (IDs 4,5), matching
            // inh_ids=(4..6) passed to the circuit builder above.
            inh_units: 200,
            units_per_chunk: 100,
            dt: 0.1,
            num_steps: 50,
            // Sustained drive (strength=10.0) guarantees spiking within 50 steps.
            input_protocol: InputProtocol::for_regime(OperatingRegime::Sustained, exc_ids.clone()),
            router: None, // LPU mode: no explicit router
            lpu_params: next_brain::lpu::aggregator::AggregatorParams::default(),
            replaced_circuit: Some(mc),
            lpu_index: None,
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
        };
        let mut config = config;

        let record = run_lpu(&mut config, &exc_ids, &inh_ids);

        // Must produce a step-level record with correct length.
        assert_eq!(record.steps.len(), 50, "LPU run must record all 50 steps");

        // At least one step must produce spikes (network is driven, not quiescent).
        // Use a diagnostic message showing mean firing rate to aid debugging.
        let any_spikes = record.steps.iter().any(|s| s.total_spikes > 0);
        assert!(
            any_spikes,
            "run_lpu() must produce spikes under Driven protocol (mean_fr={:.4}).\n\
             Check: harness unit counts ({} exc, {} inh) must match circuit chunk IDs.",
            record.mean_firing_rate(),
            config.exc_units,
            config.inh_units,
        );

        // Slot numbers must be monotonically non-decreasing.
        let slots_ordered = record.steps.windows(2).all(|w| w[1].slot >= w[0].slot);
        assert!(
            slots_ordered,
            "StepRecord::slot must be monotonically non-decreasing"
        );

        // events_injected per step must be <= 2 × num_target_chunks.
        // The corrected accounting counts at most 2 events per target (exc + inh),
        // not one per replaced edge. With 6 chunks, max = 12 events/step.
        let num_chunks = 6usize;
        for step in &record.steps {
            assert!(
                step.events_injected <= (2 * num_chunks) as u32,
                "LPU events_injected ({}) must be <= 2 × num_chunks ({}) at slot {}",
                step.events_injected,
                2 * num_chunks,
                step.slot,
            );
        }

        // Resource comparison must include LPU event count in summary.
        let comp = ResourceComparison::compute(
            &record, // use lpu as both baseline and lpu (trivial but exercises the API)
            &record, &mc2,
        );
        let s = comp.summary();
        assert!(
            !s.is_empty(),
            "ResourceComparison summary must be non-empty"
        );
        println!("{}", s);
    }

    // ── Test 10: run_lpu() produces activity after the dormancy fix ──────────────
    //
    // Before the has_active_conductance() fix (checking only g_long_range),
    // LPU proxy events written into g_local_exc went unnoticed and chunks went
    // dormant immediately. This test confirms the fix holds: an LPU run on the
    // Sustained regime must produce non-zero mean_firing_rate.
    #[test]
    fn test_run_lpu_stays_active_after_dormancy_fix() {
        use next_brain::experiment::{
            harness::{HarnessConfig, run_lpu},
            input_protocol::{InputProtocol, OperatingRegime},
        };

        let exc_ids: Vec<ChunkId> = (0..4).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6).map(ChunkId).collect();
        let mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();

        let mut config = HarnessConfig {
            exc_units: 400,
            // 200 inh units / 100 per chunk = 2 inh chunks (IDs 4,5), matching
            // inh_ids=(4..6) passed to the circuit builder above.
            inh_units: 200,
            units_per_chunk: 100,
            dt: 0.1,
            num_steps: 100,
            input_protocol: InputProtocol::for_regime(OperatingRegime::Sustained, exc_ids.clone()),
            router: None,
            lpu_params: next_brain::lpu::aggregator::AggregatorParams::default(),
            replaced_circuit: Some(mc),
            lpu_index: None,
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
        };

        let record = run_lpu(&mut config, &exc_ids, &inh_ids);
        let rate = record.mean_firing_rate();

        println!("run_lpu Sustained mean rate: {:.4}", rate);
        assert!(
            rate > 0.0,
            "run_lpu() mean rate must be > 0 under Sustained drive (was {:.6}). \
             A zero rate indicates dormancy regression (chunks going dormant after \
             proxy events written only to g_local_exc, before has_active_conductance fix).",
            rate
        );
    }

    // ── Constraint 1: split() preserves total edge count AND total weight ─────

    #[test]
    fn test_split_preserves_total_edge_count() {
        let exc_ids: Vec<ChunkId> = (0..4u32).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6u32).map(ChunkId).collect();
        let mc = EIMicrocircuitSpec::balanced(exc_ids, inh_ids).build();
        let total_before = mc.total_edge_count();

        for &ratio in &[0.0f32, 0.25, 0.50, 0.75, 1.0] {
            let (explicit_mc, lpu_mc) = mc.split_by_ratio(ratio, 42);
            let total_after = explicit_mc.total_edge_count() + lpu_mc.total_edge_count();
            assert_eq!(
                total_before, total_after,
                "split_by_ratio({ratio}) must preserve total edge count: {total_before} ≠ {total_after}"
            );
        }
    }

    #[test]
    fn test_split_preserves_total_weight_per_projection() {
        let exc_ids: Vec<ChunkId> = (0..4u32).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6u32).map(ChunkId).collect();
        let mc = EIMicrocircuitSpec::balanced(exc_ids, inh_ids).build();

        let sum_weights = |proj: &next_brain::connectivity::types::LocalProjection| -> f32 {
            proj.edges.iter().map(|e| e.weight).sum()
        };

        let ee_w = sum_weights(&mc.ee);
        let ei_w = sum_weights(&mc.ei);
        let ie_w = sum_weights(&mc.ie);
        let ii_w = sum_weights(&mc.ii);

        for &ratio in &[0.0f32, 0.25, 0.50, 0.75, 1.0] {
            let (e_mc, l_mc) = mc.split_by_ratio(ratio, 99);
            let eps = 1e-4;
            assert!(
                (sum_weights(&e_mc.ee) + sum_weights(&l_mc.ee) - ee_w).abs() < eps,
                "E→E weight not preserved at ratio={ratio}"
            );
            assert!(
                (sum_weights(&e_mc.ei) + sum_weights(&l_mc.ei) - ei_w).abs() < eps,
                "E→I weight not preserved at ratio={ratio}"
            );
            assert!(
                (sum_weights(&e_mc.ie) + sum_weights(&l_mc.ie) - ie_w).abs() < eps,
                "I→E weight not preserved at ratio={ratio}"
            );
            assert!(
                (sum_weights(&e_mc.ii) + sum_weights(&l_mc.ii) - ii_w).abs() < eps,
                "I→I weight not preserved at ratio={ratio}"
            );
        }
    }

    // ── Constraint 3: run_mixed(ratio=0) ≡ run_explicit (strict fidelity) ────

    #[test]
    fn test_mixed_mode_ratio0_equals_explicit() {
        use next_brain::experiment::harness::run_mixed;

        let exc_ids: Vec<ChunkId> = (0..4u32).map(ChunkId).collect();
        let inh_ids: Vec<ChunkId> = (4..6u32).map(ChunkId).collect();
        let n_chunks = exc_ids.len() + inh_ids.len();

        let mc = EIMicrocircuitSpec::balanced(exc_ids.clone(), inh_ids.clone()).build();
        let all_projs = mc.all_proj_refs();

        let base_cfg = HarnessConfig {
            exc_units: 400,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.001,
            num_steps: 100,
            input_protocol: InputProtocol::for_regime(
                next_brain::experiment::input_protocol::OperatingRegime::Driven,
                exc_ids.clone(),
            ),
            router: Some(EventRouter::from_projections(&all_projs, n_chunks)),
            lpu_params: next_brain::lpu::aggregator::AggregatorParams::default(),
            replaced_circuit: None,
            lpu_index: None,
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
        };

        let explicit_rec = run_explicit(&base_cfg);

        // ratio=0: split gives all edges to explicit, lpu_mc has 0 edges.
        let (explicit_mc, lpu_mc) = mc.split_by_ratio(0.0, 42);
        let all_projs2 = explicit_mc.all_proj_refs();
        let mut mixed_cfg = HarnessConfig {
            router: Some(EventRouter::from_projections(&all_projs2, n_chunks)),
            replaced_circuit: Some(lpu_mc),
            lpu_index: None,
            proxy_mode: next_brain::lpu::proxy::ProxyMode::TwoChannel,
            richer_params: next_brain::lpu::proxy_params::RicherProxyParams::default(),
            ..base_cfg
        };
        let mixed_rec = run_mixed(&mut mixed_cfg, &exc_ids, &inh_ids);

        // Constraint 3: strict event count and active chunk equivalence.
        assert_eq!(
            explicit_rec.total_events(),
            mixed_rec.total_events(),
            "run_mixed(ratio=0) total_events must equal run_explicit: {} ≠ {}",
            explicit_rec.total_events(),
            mixed_rec.total_events(),
        );
        let exp_active: f32 = explicit_rec.mean_active_chunks();
        let mix_active: f32 = mixed_rec.mean_active_chunks();
        let diff = (exp_active - mix_active).abs();
        assert!(
            diff < 0.05,
            "run_mixed(ratio=0) mean_active_chunks diverged: |{exp_active:.3} - {mix_active:.3}| = {diff:.3} > 0.05"
        );
    }
}
