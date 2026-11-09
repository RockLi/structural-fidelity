//! Phase 1 fidelity sanity checks.
//!
//! These tests compare the scalar and SIMD-friendly kernels under matched,
//! deterministic inputs. They do **not** claim full numerical fidelity for all
//! future model classes; they establish kernel-level sanity for the current
//! placeholder LIF implementation used by the Phase 1 runtime.

use next_brain::state::ChunkStateArrays;

fn make_subthreshold_state(num_units: usize) -> ChunkStateArrays {
    let mut state = ChunkStateArrays::new(num_units);
    for i in 0..num_units {
        state.voltages[i] = -70.0 + (i % 9) as f32 * 2.25;
        state.g_local_exc[i] = 4.0 + (i % 5) as f32 * 1.5;
        state.g_local_inh[i] = (i % 4) as f32 * 0.75;
        state.g_long_range[i] = 1.0 + (i % 7) as f32 * 0.5;
    }
    state
}

fn make_spiking_state(num_units: usize) -> ChunkStateArrays {
    let mut state = ChunkStateArrays::new(num_units);
    for i in 0..num_units {
        state.voltages[i] = match i % 6 {
            0 => -65.0,
            1 => -42.0,
            2 => -8.0,
            3 => 18.0,
            4 => 27.5,
            _ => 29.6,
        };
        state.g_local_exc[i] = 8.0 + (i % 11) as f32 * 6.0;
        state.g_local_inh[i] = (i % 5) as f32 * 1.25;
        state.g_long_range[i] = if i % 3 == 0 {
            48.0
        } else {
            14.0 + (i % 7) as f32 * 2.0
        };

        // Seed a subset into refractory to ensure the SIMD path matches the
        // scalar "continue" semantics for skipped units.
        if i % 13 == 0 {
            state.refractory_until[i] = 3;
            state.voltages[i] = 35.0;
            state.g_long_range[i] = 20.0;
        }
    }
    state
}

#[derive(Debug, Default)]
struct FidelitySummary {
    max_abs_voltage_error: f32,
    spike_step_mismatches: u32,
    firing_rate_deviation: f32,
}

fn run_fidelity_trial(
    initializer: fn(usize) -> ChunkStateArrays,
    num_units: usize,
    steps: u64,
) -> FidelitySummary {
    let mut scalar = initializer(num_units);
    let mut simd = initializer(num_units);

    let mut scalar_spikes = 0u32;
    let mut simd_spikes = 0u32;
    let mut max_abs_voltage_error = 0.0_f32;
    let mut spike_step_mismatches = 0u32;

    for step in 0..steps {
        scalar.step_euler(0.001, step);
        simd.step_euler_simd_friendly(0.001, step);

        for i in 0..num_units {
            let dv = (scalar.voltages[i] - simd.voltages[i]).abs();
            max_abs_voltage_error = max_abs_voltage_error.max(dv);

            let scalar_spike = scalar.spike_flags[i] > 0.5;
            let simd_spike = simd.spike_flags[i] > 0.5;
            if scalar_spike != simd_spike {
                spike_step_mismatches += 1;
            }
            scalar_spikes += scalar_spike as u32;
            simd_spikes += simd_spike as u32;
        }
    }

    let denom = (num_units as f32) * (steps as f32);
    let scalar_rate = scalar_spikes as f32 / denom;
    let simd_rate = simd_spikes as f32 / denom;

    FidelitySummary {
        max_abs_voltage_error,
        spike_step_mismatches,
        firing_rate_deviation: (scalar_rate - simd_rate).abs(),
    }
}

#[test]
fn test_scalar_vs_simd_subthreshold_trace_fidelity() {
    let summary = run_fidelity_trial(make_subthreshold_state, 256, 25);

    assert!(
        summary.max_abs_voltage_error <= 1e-6,
        "subthreshold membrane trace drift too large: {:?}",
        summary
    );
    assert_eq!(
        summary.spike_step_mismatches, 0,
        "subthreshold case should have identical spike timing: {:?}",
        summary
    );
    assert!(
        summary.firing_rate_deviation <= 1e-9,
        "subthreshold firing-rate deviation should be zero: {:?}",
        summary
    );
}

#[test]
fn test_scalar_vs_simd_spiking_fidelity() {
    let summary = run_fidelity_trial(make_spiking_state, 512, 16);

    assert!(
        summary.max_abs_voltage_error <= 1e-6,
        "spiking membrane trace drift too large: {:?}",
        summary
    );
    assert_eq!(
        summary.spike_step_mismatches, 0,
        "spike timing mismatch between scalar and SIMD paths: {:?}",
        summary
    );
    assert!(
        summary.firing_rate_deviation <= 1e-9,
        "firing-rate deviation should be zero for matched kernels: {:?}",
        summary
    );
}
