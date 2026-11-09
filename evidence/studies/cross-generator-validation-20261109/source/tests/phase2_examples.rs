//! Phase 2 integration tests: Task 8 Example Use Cases.
//!
//! Validates that:
//! (a) E/I stability sweep produces qualitatively distinct regimes.
//! (b) Panic motif shows runaway onset and phase-level rate differentiation.
//! (c) CSV export is non-empty and well-formed.
//! (d) RegimeRun only covers configured regimes (None for unconfigured).

#[cfg(test)]
mod phase2_examples {
    use next_brain::examples::{
        ei_stability::{EIStabilityConfig, Regime, run_stability_sweep},
        panic_motif::{PanicMotifConfig, PanicPhase, run_panic_motif},
    };

    // ── Test 1: Runaway produces STRICTLY higher activity than Quiescent ──────────
    //
    // Root cause of previous identical rates: drive=40 → g_exc_ss≈400 completely
    // drowns inhibitory feedback (w_ie=3.0 → g_inh_ss≈9.6 = 2.4% of drive).
    //
    // Fix: use calibrated E→I parameters (w_ei=20, p_ei=0.8) so inh chunks fire,
    // and extreme w_ie values (Q=50, R=0.01) so I→E feedback visibly suppresses exc.
    // drive=8.0 → g_exc_ss=80 → exc_rate≈10%; strong enough for inh feedback to matter.
    #[test]
    fn test_stability_regimes_ordering() {
        let cfg = EIStabilityConfig {
            exc_units: 200,
            inh_units: 50,
            units_per_chunk: 50,
            dt: 0.1,
            num_steps: 300,
            drive_strength: 8.0,
            w_ei: 20.0,
            p_ie: 1.0,
            p_ei: 0.8,
            regimes: vec![Regime::Quiescent, Regime::Oscillatory, Regime::Runaway],
        };

        let result = run_stability_sweep(&cfg);
        let q = result.quiescent.as_ref().expect("Quiescent not run");
        let o = result.oscillatory.as_ref().expect("Oscillatory not run");
        let r = result.runaway.as_ref().expect("Runaway not run");

        println!("{}", q.summary());
        println!("{}", o.summary());
        println!("{}", r.summary());

        // All regimes must produce non-trivial spiking.
        assert!(
            q.peak_exc_rate() > 0.0,
            "Quiescent must spike (peak=0 → network dormant)"
        );
        assert!(r.peak_exc_rate() > 0.0, "Runaway must spike");

        // Runaway (w_ie=0.2: minimal inhibition) must fire STRICTLY more than
        // Quiescent (w_ie=3.0: strong inhibition).
        // This is the core paper claim: E/I balance controls excitatory rate.
        assert!(
            r.mean_exc_rate() > q.mean_exc_rate(),
            "Runaway mean ({:.4}) must STRICTLY exceed Quiescent mean ({:.4}).\n\
             If rates are identical, inhibitory feedback is not reaching excitatory chunks.\n\
             Check: (a) I→E edges exist, (b) inh chunks spike, (c) event routing sign is correct.",
            r.mean_exc_rate(),
            q.mean_exc_rate()
        );

        // Monotonicity: Oscillatory must lie between Quiescent and Runaway.
        assert!(
            o.mean_exc_rate() >= q.mean_exc_rate(),
            "Oscillatory mean ({:.4}) must be >= Quiescent ({:.4})",
            o.mean_exc_rate(),
            q.mean_exc_rate()
        );
    }

    #[test]
    fn test_regime_selection_respected() {
        let cfg = EIStabilityConfig {
            exc_units: 100,
            inh_units: 25,
            units_per_chunk: 25,
            dt: 0.1,
            num_steps: 20,
            drive_strength: 1.5,
            w_ei: 20.0,
            p_ie: 1.0,
            p_ei: 0.8,
            regimes: vec![Regime::Oscillatory], // Only oscillatory
        };
        let result = run_stability_sweep(&cfg);

        assert!(
            result.quiescent.is_none(),
            "Quiescent should be None (not requested)"
        );
        assert!(result.oscillatory.is_some(), "Oscillatory should be Some");
        assert!(
            result.runaway.is_none(),
            "Runaway should be None (not requested)"
        );
    }

    // ── Test 3: StabilityResult CSV export is well-formed ────────────────────────
    #[test]
    fn test_stability_csv_export() {
        let cfg = EIStabilityConfig {
            exc_units: 100,
            inh_units: 25,
            units_per_chunk: 25,
            dt: 0.1,
            num_steps: 20,
            drive_strength: 1.5,
            w_ei: 20.0,
            p_ie: 1.0,
            p_ei: 0.8,
            regimes: vec![Regime::Quiescent, Regime::Runaway],
        };
        let result = run_stability_sweep(&cfg);
        let csv = result.to_csv();

        let lines: Vec<&str> = csv.lines().collect();
        assert!(
            lines.len() > 1,
            "CSV must have header + data rows, got {}",
            lines.len()
        );
        assert_eq!(lines[0], "regime,slot,exc_rate,inh_spikes,active_chunks");

        // Every data row: 5 comma-separated fields.
        for row in &lines[1..] {
            let fields: Vec<&str> = row.split(',').collect();
            assert_eq!(fields.len(), 5, "CSV row must have 5 fields: {:?}", row);
        }

        // Only configured regimes appear.
        let regime_labels: Vec<&str> = lines[1..]
            .iter()
            .map(|r| r.split(',').next().unwrap())
            .collect();
        assert!(
            regime_labels.contains(&"Quiescent"),
            "Quiescent rows missing"
        );
        assert!(regime_labels.contains(&"Runaway"), "Runaway rows missing");
        assert!(
            !regime_labels.contains(&"Oscillatory"),
            "Oscillatory was not requested"
        );
    }

    // ── Test 4: Panic motif has three phases with correct step counts ─────────────
    #[test]
    fn test_panic_motif_three_phases() {
        // Units_per_chunk must divide exactly into inh_units for matching IDs.
        // Using defaults picks up the calibrated w_ei/p_ie/p_ei automatically.
        let cfg = PanicMotifConfig {
            exc_units: 200,
            inh_units: 100,
            units_per_chunk: 100, // 2 exc chunks (0-1) + 1 inh chunk (2)
            dt: 0.1,
            baseline_steps: 30,
            perturbation_steps: 30,
            recovery_steps: 30,
            ..PanicMotifConfig::default() // picks up drive=8.0, w_ie=300, p_ie=1.0
        };

        let result = run_panic_motif(&cfg);

        let n_baseline = result
            .trajectory
            .iter()
            .filter(|s| s.phase == PanicPhase::Baseline)
            .count();
        let n_perturb = result
            .trajectory
            .iter()
            .filter(|s| s.phase == PanicPhase::Perturbation)
            .count();
        let n_recovery = result
            .trajectory
            .iter()
            .filter(|s| s.phase == PanicPhase::Recovery)
            .count();

        assert_eq!(n_baseline, 30, "Expected 30 baseline steps");
        assert_eq!(n_perturb, 30, "Expected 30 perturbation steps");
        assert_eq!(n_recovery, 30, "Expected 30 recovery steps");
    }

    // ── Test 5: Perturbation (weakened inhibition) has strictly higher activity ───
    //
    // Central paper claim: disinhibition causes runaway excitation.
    // Asserts:
    //   (a) perturb_mean > baseline_mean
    //   (b) runaway_onset_slot is detected (rate crosses 2× baseline within perturbation)
    #[test]
    fn test_panic_perturbation_exceeds_baseline() {
        let cfg = PanicMotifConfig {
            exc_units: 200,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            baseline_steps: 100,
            perturbation_steps: 100,
            recovery_steps: 50,
            ..PanicMotifConfig::default() // drive=8.0, baseline_w_ie=300, panic_w_ie=0.001
        };

        let result = run_panic_motif(&cfg);
        let baseline_mean = result.mean_exc_rate_by_phase(PanicPhase::Baseline);
        let perturb_mean = result.mean_exc_rate_by_phase(PanicPhase::Perturbation);

        println!("Baseline mean: {:.4}", baseline_mean);
        println!("Perturbation mean: {:.4}", perturb_mean);
        println!(
            "Perturbation peak: {:.4}",
            result.peak_exc_rate_perturbation()
        );
        println!("Runaway onset slot: {:?}", result.runaway_onset_slot());

        // (a) Disinhibition drives more excitatory spiking.
        assert!(
            perturb_mean > baseline_mean,
            "Perturbation mean ({:.4}) must exceed Baseline mean ({:.4}).\n\
             If equal, inhibitory feedback is not modulating excitatory activity.",
            perturb_mean,
            baseline_mean,
        );

        // (b) Runaway onset must be detected: at least one step in Perturbation
        //     where exc_rate > 2× baseline_mean. With baseline≈3.7% and runaway≈12.7%,
        //     the ratio is ≈3.4× so onset should be detected within a few steps.
        assert!(
            result.runaway_onset_slot().is_some(),
            "Runaway onset must be detected (no step in Perturbation exceeded 2× baseline={:.4}).\n\
             Check: baseline_w_ie ({:.1}) must be strong enough to suppress baseline rate;\
             panic_w_ie ({:.4}) must remove that suppression.",
            baseline_mean,
            cfg.baseline_w_ie,
            cfg.panic_w_ie,
        );
    }

    // ── Test 5b: Recovery brings activity back toward baseline ─────────────────
    //
    // Validates the third phase of the panic motif: restoring inhibitory weight
    // must produce measurable rate suppression. Asserts:
    //   (a) partial_recovery_achieved(): recovery_mean < 1.5 × baseline_mean
    //   (b) recovery_mean < perturb_mean (directional correctness)
    #[test]
    fn test_panic_recovery_partial_recovery() {
        let cfg = PanicMotifConfig {
            exc_units: 200,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            baseline_steps: 100,
            perturbation_steps: 100,
            // Long recovery window so the inhibitory suppression can fully express.
            recovery_steps: 150,
            ..PanicMotifConfig::default()
        };

        let result = run_panic_motif(&cfg);
        let baseline_mean = result.mean_exc_rate_by_phase(PanicPhase::Baseline);
        let perturb_mean = result.mean_exc_rate_by_phase(PanicPhase::Perturbation);
        let recovery_mean = result.mean_exc_rate_by_phase(PanicPhase::Recovery);

        result.print_summary();

        // (a) Recovery mean must be within 150% of baseline (paper tolerance).
        assert!(
            result.partial_recovery_achieved(),
            "partial_recovery_achieved() must be true.\n\
             recovery_mean={:.4}, baseline_mean={:.4}, threshold=1.5×baseline={:.4}.\n\
             If NO/INCOMPLETE: the inhibitory restoration does not suppress runaway.\
             Check p_ie ({:.1}) and baseline_w_ie ({:.1}) calibration.",
            recovery_mean,
            baseline_mean,
            baseline_mean * 1.5,
            cfg.p_ie,
            cfg.baseline_w_ie,
        );

        assert!(
            recovery_mean < perturb_mean,
            "Recovery mean ({:.4}) must be < Perturbation mean ({:.4}).",
            recovery_mean,
            perturb_mean,
        );
    }

    // ── Test 6: Panic motif CSV is well-formed ──────────────────────────────────
    #[test]
    fn test_panic_motif_csv_export() {
        let cfg = PanicMotifConfig {
            exc_units: 400,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            baseline_steps: 10,
            perturbation_steps: 10,
            recovery_steps: 10,
            ..PanicMotifConfig::default()
        };

        let result = run_panic_motif(&cfg);
        let csv = result.to_csv();
        let lines: Vec<&str> = csv.lines().collect();

        assert_eq!(lines[0], "phase,slot,exc_rate,inh_spikes,active_chunks");
        assert_eq!(lines.len(), 31, "Expected 31 lines (header + 30 data rows)");

        let valid_phases = ["Baseline", "Perturbation", "Recovery"];
        for row in &lines[1..] {
            let phase = row.split(',').next().unwrap();
            assert!(
                valid_phases.contains(&phase),
                "Unknown phase label: {}",
                phase
            );
        }
    }

    // ── Test 7: print_summary does not panic ──────────────────────────────
    #[test]
    fn test_panic_summary_no_panic() {
        let result = run_panic_motif(&PanicMotifConfig {
            exc_units: 400,
            inh_units: 100,
            units_per_chunk: 100,
            dt: 0.1,
            baseline_steps: 10,
            perturbation_steps: 10,
            recovery_steps: 10,
            ..PanicMotifConfig::default()
        });
        result.print_summary();
    }

    // ── Test 8: print_table works and network produces non-trivial output ────────
    #[test]
    fn test_stability_table_no_panic() {
        let cfg = EIStabilityConfig {
            exc_units: 40,
            inh_units: 10,
            units_per_chunk: 10,
            dt: 0.1,
            num_steps: 50,
            drive_strength: 8.0,
            w_ei: 20.0,
            p_ie: 1.0,
            p_ei: 0.8,
            regimes: vec![Regime::Quiescent, Regime::Oscillatory, Regime::Runaway],
        };
        let result = run_stability_sweep(&cfg);
        result.print_table(); // Must not panic.
        // At least one regime must show non-zero peak activity.
        let any_active = [&result.quiescent, &result.oscillatory, &result.runaway]
            .iter()
            .filter_map(|r| r.as_ref())
            .any(|r| r.peak_exc_rate() > 0.0);
        assert!(
            any_active,
            "print_table smoke test: at least one regime must spike"
        );
    }
}
