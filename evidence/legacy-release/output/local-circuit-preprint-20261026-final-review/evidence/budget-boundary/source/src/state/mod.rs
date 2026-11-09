pub mod aos_baseline;
pub mod block_soa;

/// Structure of Arrays (SoA) layout for chunk-local neural state.
///
/// Each field is a contiguous `f32` array of length `num_units`.
/// Index `i` consistently refers to the same unit across all arrays.
///
/// # LPU Compatibility Note
/// The `g_local_exc`, `g_local_inh`, and `g_long_range` channels are included
/// for LPU-compatible state layout. Phase 1 does **not** validate Local Proxy Unit
/// replacement dynamics; these channels are placeholders to avoid structural
/// refactoring in later phases.
#[derive(Debug)]
pub struct ChunkStateArrays {
    /// Number of units allocated in this chunk.
    pub num_units: usize,
    /// Membrane potential V_m for each unit (mV).
    pub voltages: Vec<f32>,
    /// Recovery variable u for each unit (Izhikevich-style).
    pub recovery: Vec<f32>,
    /// Local excitatory conductance g_local_exc for each unit.
    pub g_local_exc: Vec<f32>,
    /// Local inhibitory conductance g_local_inh for each unit.
    pub g_local_inh: Vec<f32>,
    /// Long-range input channel g_long_range for each unit.
    pub g_long_range: Vec<f32>,
    /// Spike flag (1.0 = fired this step, 0.0 = silent) for each unit.
    pub spike_flags: Vec<f32>,
    /// Timestep at which refractory period expires for each unit.
    /// Stored as `u64` to match `Scheduler::current_slot` and avoid wrap-around
    /// at ~71 min simulated time when using `dt = 0.001`.
    pub refractory_until: Vec<u64>,
}

impl ChunkStateArrays {
    /// Allocate a new `ChunkStateArrays` for `num_units` units.
    /// All state is zero-initialized.
    pub fn new(num_units: usize) -> Self {
        Self {
            num_units,
            voltages: vec![-65.0_f32; num_units], // Resting potential
            recovery: vec![0.0_f32; num_units],
            g_local_exc: vec![0.0_f32; num_units],
            g_local_inh: vec![0.0_f32; num_units],
            g_long_range: vec![0.0_f32; num_units],
            spike_flags: vec![0.0_f32; num_units],
            refractory_until: vec![0_u64; num_units],
        }
    }

    /// Apply a single Euler update step to all units (SoA bulk update).
    ///
    /// This is a minimal placeholder kernel for Phase 1 benchmarking only.
    /// Uses a simplified leaky integration: `dV = (-V + I_syn) * dt`.
    pub fn step_euler(&mut self, dt: f32, current_step: u64) {
        let num = self.num_units;
        for i in 0..num {
            // Skip units in refractory period.
            if self.refractory_until[i] > current_step {
                self.spike_flags[i] = 0.0;
                continue;
            }

            // Minimal I_syn: sum of conductance channels driving membrane.
            let i_syn = self.g_local_exc[i] - self.g_local_inh[i] + self.g_long_range[i];
            let dv = (-self.voltages[i] + i_syn) * dt;
            self.voltages[i] += dv;

            self.g_local_exc[i] *= 1.0 - dt;
            self.g_local_inh[i] *= 1.0 - dt;
            self.g_long_range[i] *= 1.0 - dt;

            if self.voltages[i] >= 30.0 {
                self.spike_flags[i] = 1.0;
                self.voltages[i] = -65.0;
                self.refractory_until[i] = current_step + 2;
            } else {
                self.spike_flags[i] = 0.0;
            }
        }
    }

    /// Apply a single Euler update step using branchless arithmetic (SIMD-friendly).
    ///
    /// Branches are the primary blocker for LLVM auto-vectorization. This version
    /// replaces all `if/continue` patterns with conditional multipliers and
    /// floating-point select operations, allowing the compiler to emit AVX/AVX2
    /// instructions on supported CPUs.
    ///
    /// Requires `RUSTFLAGS="-C target-cpu=native"` to unlock AVX2/AVX-512 on x86.
    ///
    /// # Why branches block SIMD
    /// - `if refractory > step { continue }` — data-dependent loop exit prevents
    ///   uniform lane execution. Vector units need all N lanes to run identical ops.
    /// - `if voltage >= 30.0 { ... }` — divergent stores (some lanes write reset,
    ///   others don't) cannot be expressed as a single VMOVAPS without masking.
    ///
    /// # Branchless substitutions used here
    /// - Refractory gate: `(refractory <= step) as u32 as f32` → 0.0 or 1.0 mask
    /// - Spike select:    `fired * v_reset + (1 - fired) * v_current` → VBLENDVPS
    pub fn step_euler_simd_friendly(&mut self, dt: f32, current_step: u64) {
        let num = self.num_units;
        let v_thresh = 30.0_f32;
        let v_reset = -65.0_f32;

        for i in 0..num {
            // Refractory gate: 1.0 = active, 0.0 = in refractory.
            let active_u32 = (self.refractory_until[i] <= current_step) as u32;
            let active = active_u32 as f32;

            // Input current gated by active mask.
            let i_syn = (self.g_local_exc[i] - self.g_local_inh[i] + self.g_long_range[i]) * active;

            // Voltage update gated by active mask.
            self.voltages[i] += (-self.voltages[i] + i_syn) * dt * active;

            // Match scalar semantics: refractory units skip the whole update,
            // including conductance decay.
            let decay = 1.0_f32 - dt * active;
            self.g_local_exc[i] *= decay;
            self.g_local_inh[i] *= decay;
            self.g_long_range[i] *= decay;

            // Branchless spike + reset: LLVM emits VCMPPS + VBLENDVPS.
            let fired = ((self.voltages[i] >= v_thresh) as u32) * active_u32;
            let fired_f = fired as f32;
            self.voltages[i] = fired_f * v_reset + (1.0 - fired_f) * self.voltages[i];
            self.spike_flags[i] = fired_f;
            // Set refractory window to an absolute future slot (branchless select).
            // fired=1 → refractory_until = current_step + 2
            // fired=0 → refractory_until unchanged
            self.refractory_until[i] =
                fired as u64 * (current_step + 2) + (1 - fired as u64) * self.refractory_until[i];
        }
    }

    /// Selective kernel: Scan and update spike flags only.
    ///
    /// Demonstrates SoA selective access: only loads `spike_flags`, `refractory_until`,
    /// and `voltages` — 3 arrays instead of 7. Cache working set is 60% smaller vs AoS.
    pub fn step_spikes_only(&mut self, current_step: u64) -> u32 {
        let mut spike_count = 0u32;
        for i in 0..self.num_units {
            if self.refractory_until[i] > current_step {
                self.spike_flags[i] = 0.0;
                continue;
            }
            if self.voltages[i] >= 30.0 {
                self.spike_flags[i] = 1.0;
                self.voltages[i] = -65.0;
                self.refractory_until[i] = current_step + 2;
                spike_count += 1;
            } else {
                self.spike_flags[i] = 0.0;
            }
        }
        spike_count
    }

    /// Selective kernel: Update voltages and conductances only (branch-free).
    ///
    /// No branches — this loop is trivially auto-vectorizable by LLVM even
    /// without `target-cpu=native`, as it contains only uniform f32 arithmetic.
    pub fn step_voltages_only(&mut self, dt: f32, _current_step: u64) {
        let decay = 1.0_f32 - dt;
        for i in 0..self.num_units {
            let i_syn = self.g_local_exc[i] - self.g_local_inh[i] + self.g_long_range[i];
            self.voltages[i] += (-self.voltages[i] + i_syn) * dt;
            self.g_local_exc[i] *= decay;
            self.g_local_inh[i] *= decay;
            self.g_long_range[i] *= decay;
        }
    }

    /// Returns total memory footprint in bytes for all state arrays.
    pub fn memory_bytes(&self) -> usize {
        let f32_arrays = 6; // voltages, recovery, g_local_exc, g_local_inh, g_long_range, spike_flags
        let u64_arrays = 1; // refractory_until (u64 to avoid slot wrap-around)
        self.num_units
            * (f32_arrays * std::mem::size_of::<f32>() + u64_arrays * std::mem::size_of::<u64>())
    }

    /// Returns `true` if any unit has a non-negligible long-range conductance.
    /// Returns `true` if any conductance channel still has meaningful energy.
    ///
    /// Checks all three channels so that subthreshold input in ANY channel keeps
    /// the chunk alive for further decay steps:
    /// - `g_local_exc`: excitatory local micro-edges and external tonic drive.
    /// - `g_local_inh`: inhibitory local micro-edges.
    /// - `g_long_range`: afferent / long-range inputs.
    #[inline]
    pub fn has_active_conductance(&self, epsilon: f32) -> bool {
        self.g_local_exc.iter().any(|&g| g > epsilon)
            || self.g_local_inh.iter().any(|&g| g > epsilon)
            || self.g_long_range.iter().any(|&g| g.abs() > epsilon)
    }
}
