/// Array of Structures (AoS) layout — used as the Benchmark A comparison baseline.
///
/// This is a deliberately naïve layout: each unit is stored as a compact struct.
/// It serves as the control condition in the data-layout benchmark, not as a
/// production-grade component of the runtime.
#[derive(Debug, Clone, Copy)]
pub struct NeuronAoS {
    pub voltage: f32,
    pub recovery: f32,
    pub g_local_exc: f32,
    pub g_local_inh: f32,
    pub g_long_range: f32,
    pub spike_flag: f32,
    pub refractory_until: u64,
}

impl Default for NeuronAoS {
    fn default() -> Self {
        Self {
            voltage: -65.0,
            recovery: 0.0,
            g_local_exc: 0.0,
            g_local_inh: 0.0,
            g_long_range: 0.0,
            spike_flag: 0.0,
            refractory_until: 0,
        }
    }
}

/// AoS baseline unit array for benchmark A.
#[derive(Debug)]
pub struct AosStateBaseline {
    pub units: Vec<NeuronAoS>,
}

impl AosStateBaseline {
    pub fn new(num_units: usize) -> Self {
        Self {
            units: vec![NeuronAoS::default(); num_units],
        }
    }

    /// Single Euler update step — semantically identical to [`ChunkStateArrays::step_euler`].
    pub fn step_euler(&mut self, dt: f32, current_step: u64) {
        for neuron in self.units.iter_mut() {
            if neuron.refractory_until > current_step {
                neuron.spike_flag = 0.0;
                continue;
            }

            let i_syn = neuron.g_local_exc - neuron.g_local_inh + neuron.g_long_range;
            let dv = (-neuron.voltage + i_syn) * dt;
            neuron.voltage += dv;

            neuron.g_local_exc *= 1.0 - dt;
            neuron.g_local_inh *= 1.0 - dt;
            neuron.g_long_range *= 1.0 - dt;

            if neuron.voltage >= 30.0 {
                neuron.spike_flag = 1.0;
                neuron.voltage = -65.0;
                neuron.refractory_until = current_step + 2;
            } else {
                neuron.spike_flag = 0.0;
            }
        }
    }

    /// Selective equivalent scan: Checks and updates spike flags.
    /// In AoS, this still touches the full struct per iterate.
    pub fn step_spikes_only(&mut self, current_step: u64) -> u32 {
        let mut spike_count = 0;
        for neuron in self.units.iter_mut() {
            if neuron.refractory_until > current_step {
                neuron.spike_flag = 0.0;
                continue;
            }

            if neuron.voltage >= 30.0 {
                neuron.spike_flag = 1.0;
                neuron.voltage = -65.0;
                neuron.refractory_until = current_step + 2;
                spike_count += 1;
            } else {
                neuron.spike_flag = 0.0;
            }
        }
        spike_count
    }

    /// Selective equivalent update: Updates voltages only.
    /// In AoS, this still touches the full struct per iterate.
    pub fn step_voltages_only(&mut self, dt: f32, _current_step: u64) {
        for neuron in self.units.iter_mut() {
            let i_syn = neuron.g_local_exc - neuron.g_local_inh + neuron.g_long_range;
            let dv = (-neuron.voltage + i_syn) * dt;
            neuron.voltage += dv;

            neuron.g_local_exc *= 1.0 - dt;
            neuron.g_local_inh *= 1.0 - dt;
            neuron.g_long_range *= 1.0 - dt;
        }
    }

    /// Returns total memory footprint in bytes.
    pub fn memory_bytes(&self) -> usize {
        self.units.len() * std::mem::size_of::<NeuronAoS>()
    }

    /// Returns `true` if any unit has a non-negligible long-range conductance.
    /// Mirrors `ChunkStateArrays::has_active_conductance` for the AoS path.
    #[inline]
    pub fn has_active_conductance(&self, epsilon: f32) -> bool {
        self.units.iter().any(|n| n.g_long_range.abs() > epsilon)
    }
}
