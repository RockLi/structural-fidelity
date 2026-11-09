"""Source-verified reproducibility tables; main connected workloads only.

Audited 2026-10-22 against /Users/rock/workspace/bettiai/brian2/next-brain.
This file contains protocol metadata, not newly measured results.
Probability/weight tuple order is ALWAYS (EE, EI, IE, II), unlike the
regime_cases tuple declaration in the Rust tests (EE, IE, EI, II).
"""

SOURCE_ROOT = '/Users/rock/workspace/bettiai/brian2/next-brain'
EDGE_ORDER = ('EE', 'EI', 'IE', 'II')
DT_MS = 0.1
DT_S = DT_MS / 1000.0
UNITS_PER_CHUNK = 100
EDGE_DELAY_SLOTS = 1
LOCAL_FIELD_TAU_MS = 10.0

COMMON_PROTOCOL = {
    'dt_ms': DT_MS,
    'dt_s_for_metrics': DT_S,
    'units_per_chunk': UNITS_PER_CHUNK,
    'edge_delay_slots': EDGE_DELAY_SLOTS,
    'input_delay_slots': 0,
    'input_targets': 'All excitatory chunks',
    'initial_voltage': -65.0,
    'initial_other_state': 0.0,
    'local_field_tau_ms': LOCAL_FIELD_TAU_MS,
    'source': 'tests/phase3_benchmarks.rs:39-46; src/experiment/harness.rs:150-208; src/state/mod.rs:39-48',
}

BALANCED_P = (0.10, 0.20, 0.20, 0.15)
BALANCED_W = (0.8, 0.8, 1.2, 0.6)
E3_P = (0.15, 0.25, 0.25, 0.20)
E3_W = (0.6, 0.8, 1.4, 0.5)
E3_BUDGET_THRESHOLDS = (2.0, 1.75, 1.4, 1.1, 0.8)

# Policy IDs below are deliberately shorter than the misleading historical API names.
POLICIES = [
    {
        'id': 'P-I',
        'label': 'Inhibitory-source threshold',
        'api_identifier': 'StrongInhibitoryLoop',
        'predicate': 'source is inhibitory AND weight >= theta',
        'cutoffs': 'E1/E1calib/E3homo: 1.0; E3hetero main: 1.4; E3 budget: 2.0, 1.75, 1.4, 1.1, 0.8; E3 policy comparison: 1.0; E4: 0.8*w_IE; E5: 1.5',
        'qualification': 'No target-E, reciprocal-edge, or cycle requirement.',
        'source': 'src/experiment/retention.rs:144-149',
    },
    {
        'id': 'P-II',
        'label': 'I-to-I threshold',
        'api_identifier': 'FastInhibitoryLoop',
        'predicate': 'source is inhibitory AND target is inhibitory AND weight >= 0.25',
        'cutoffs': '0.25 in the E3 policy comparison',
        'qualification': 'No propagation-speed, reciprocity, or cycle requirement.',
        'source': 'src/experiment/retention.rs:162-169; tests/phase3_benchmarks.rs:2582',
    },
    {
        'id': 'P-EI',
        'label': 'E-to-I threshold',
        'api_identifier': 'ShortCycleMotif',
        'predicate': 'source is excitatory AND target is inhibitory AND weight >= 0.70',
        'cutoffs': '0.70 in the E3 policy comparison',
        'qualification': 'No reverse-edge or cycle requirement.',
        'source': 'src/experiment/retention.rs:171-178; tests/phase3_benchmarks.rs:2583',
    },
    {
        'id': 'P-UNION',
        'label': 'Union of inhibitory selections',
        'api_identifier': 'StrongInh+FastInh',
        'predicate': '(source is inhibitory AND weight >= 1.0) OR (source is inhibitory AND target is inhibitory AND weight >= 0.25)',
        'cutoffs': 'P-I: 1.0; P-II: 0.25',
        'qualification': 'Set union; matching an edge twice does not duplicate it. First matching class returns true.',
        'source': 'src/experiment/retention.rs:141-180; tests/phase3_benchmarks.rs:2584-2597',
    },
]


def _workload(identifier, label, exc, inh, steps, p, w, seed, spread,
              retention, source, input_description='Tonic amplitude 10 at every slot',
              forbid_within_chunk=False):
    return {
        'id': identifier, 'label': label,
        'exc_units': exc, 'inh_units': inh, 'total_units': exc + inh,
        'exc_chunks': exc // UNITS_PER_CHUNK,
        'inh_chunks': inh // UNITS_PER_CHUNK,
        'total_chunks': (exc + inh) // UNITS_PER_CHUNK,
        'units_per_chunk': UNITS_PER_CHUNK,
        'steps': steps, 'duration_ms': steps * DT_MS, 'dt_ms': DT_MS,
        'probabilities_EE_EI_IE_II': p,
        'base_weights_EE_EI_IE_II': w,
        'rng_seed': seed, 'weight_spread_fraction': spread,
        'forbid_within_chunk_flag': forbid_within_chunk,
        'edge_delay_slots': EDGE_DELAY_SLOTS,
        'retention': retention, 'input': input_description, 'source': source,
    }


WORKLOADS = [
    _workload('E1', 'E1 sustained', 40000, 10000, 500, BALANCED_P,
              BALANCED_W, 42, 0.0, 'Pure: none; hybrid: P-I theta=1.0',
              'tests/phase3_benchmarks.rs:2303-2367; src/connectivity/microcircuit.rs:84-99'),
    _workload('E1calib', 'E1 medium calibration and parameter island',
              10000, 2500, 200, BALANCED_P, BALANCED_W, 42, 0.0,
              'P-I theta=1.0; gains scanned as CALIBRATION_GRIDS',
              'tests/phase3_benchmarks.rs:1177-1259,2057-2112,2630-2689'),
    _workload('E3hetero', 'E3 heterogeneous main hybrid',
              10000, 2500, 200, E3_P, E3_W, 200, 0.50,
              'P-I theta=1.4',
              'tests/phase3_benchmarks.rs:2383-2433; src/connectivity/microcircuit.rs:113-128',
              forbid_within_chunk=True),
    _workload('E3budget', 'E3 heterogeneous retention-budget sweep',
              10000, 2500, 200, E3_P, E3_W, 200, 0.50,
              'None (0%); P-I theta in (2.0, 1.75, 1.4, 1.1, 0.8)',
              'tests/phase3_benchmarks.rs:2534-2577; evidence/scripts/reproduce_e3_zero.py', forbid_within_chunk=True),
    _workload('E3policies', 'E3 heterogeneous edge-class comparison',
              10000, 2500, 200, E3_P, E3_W, 200, 0.50,
              'P-I theta=1.0; P-II theta=0.25; P-EI theta=0.70; P-UNION as defined in S1',
              'tests/phase3_benchmarks.rs:2579-2628', forbid_within_chunk=True),
    _workload('E3homo', 'E3 homogeneous hybrid',
              10000, 2500, 300, E3_P, E3_W, 99, 0.0,
              'P-I theta=1.0',
              'tests/phase3_benchmarks.rs:2455-2517', forbid_within_chunk=True),
    _workload('E4stable', 'E4 stable weight setting',
              4000, 1000, 200, BALANCED_P, (0.3, 0.5, 1.6, 0.3), 42, 0.0,
              'P-I theta=0.8*w_IE=1.28 (expression evaluated in f32)',
              'tests/phase3_benchmarks.rs:2802-2879'),
    _workload('E4balanced', 'E4 balanced weight setting',
              4000, 1000, 200, BALANCED_P, BALANCED_W, 42, 0.0,
              'P-I theta=0.8*w_IE=0.96 (expression evaluated in f32)',
              'tests/phase3_benchmarks.rs:2802-2879'),
    _workload('E4excitable', 'E4 excitable weight setting',
              4000, 1000, 200, BALANCED_P, (1.2, 1.0, 0.8, 0.4), 42, 0.0,
              'P-I theta=0.8*w_IE=0.64 (expression evaluated in f32)',
              'tests/phase3_benchmarks.rs:2802-2879'),
    _workload('E5', 'E5 perturbation and recovery',
              4000, 1000, 300, (0.10, 0.30, 0.30, 0.15),
              (0.3, 1.0, 1.8, 0.4), 55, 0.0,
              'P-I theta=1.5',
              'tests/phase3_benchmarks.rs:2894-2969',
              input_description='Amplitude 150 in slots 0-79 (8 ms); zero external input in slots 80-299 (22 ms). Pulse generator on_slots=80, off_slots=22000; no second pulse occurs.'),
]

CALIBRATION_GRIDS = [
    {'label': 'Medium grid', 'gain_fast_exc': (1.0, 2.5, 5.0),
     'gain_fast_inh': (0.1, 0.4, 0.8), 'evaluations_per_mode': 9},
    {'label': 'Local island', 'gain_fast_exc': (2.0, 2.5, 3.0),
     'gain_fast_inh': (0.30, 0.40, 0.50), 'evaluations_per_mode': 9},
]
CALIBRATION_NOTE = ('Both the filtered four-channel and history-modulated modes use these grids. '
                    'The pair (2.5, 0.4) occurs twice: 18 evaluations, 17 distinct pairs per mode. '
                    'Slow gains and all time constants retain their defaults.')

PROXY_PARAMETERS = {
    'channel_order': ('E_fast', 'E_slow', 'I_fast', 'I_slow'),
    'tau_ms': (3.0, 80.0, 7.0, 80.0),
    'four_channel_default_gains': (1.0, 0.5, 1.0, 0.3),
    'four_channel_normalize_by_population': True,
    'principal_history_mode_fast_gains': (2.5, 0.4),
    'principal_history_mode_actual_kappa': (0.9925, 1.003),
    'history_mode_slow_gains_ignored': True,
    'history_mode_population_normalization_switch_ignored': True,
    'history_alpha': 'clamp(dt_ms/20, 0.005, 0.25)',
    'contrast_epsilon': 0.001,
    'source': 'src/lpu/proxy_params.rs:65-80; src/experiment/lpu_index.rs:331-435',
}

PROTOCOL_NOTES = [
    'All units per chunk share initial state, parameters and broadcast inputs; chunk IDs allocate all E chunks first, then I chunks.',
    'The builder visits projection arms in EE, EI, IE, II order; each accepted heterogeneous edge consumes an additional weight draw from the same LCG.',
    'Weight spread 0.50 means w = base_weight * Uniform(0.5, 1.5). A different spread can change both weights and subsequently sampled edges.',
    'EE and II self-chunk edges are excluded regardless of forbid_within_chunk; E and I sets are disjoint. All generated edges cross chunks.',
    'Stored delay d=1 gives post-step explicit/history-mode delivery at n+2 for a spike emitted in slot n; legacy proxy delivery is n+1.',
    'Raw-sum diagnostic copies inherit the paired workload and retained set; they change delivered magnitude, not graph selection or physical step.',
    'External-input events are excluded from reported internally routed message counts. Counts are enqueue counts, including messages still pending at the run boundary.',
    'No spectral-export workload is included in this table; those old exports have a distinct time-unit/provenance problem and are excluded from main results.',
]

# Compact ready-to-render tables; rich WORKLOADS above preserve exact machine-readable values.
S1_HEADERS = ('ID / historical API label', 'Implemented membership test', 'Cutoffs in policy comparison')
S1_ROWS = [
    ('P-I / StrongInhibitoryLoop', 'Inhibitory source AND w >= theta; any target', 'theta=1.0 in E3 policy comparison'),
    ('P-II / FastInhibitoryLoop', 'Inhibitory source AND inhibitory target AND w >= theta', 'theta=0.25'),
    ('P-EI / ShortCycleMotif', 'Excitatory source AND inhibitory target AND w >= theta', 'theta=0.70'),
    ('P-UNION / StrongInh+FastInh', '(I source AND w >= 1.0) OR (I source AND I target AND w >= 0.25)', 'Union; each retained edge appears once'),
]
S1_NOTE = ('None of these tests checks reciprocity, a graph cycle, or propagation speed. '
           'The P-I threshold is workload-specific; see the protocol rows.')

WORKLOAD_TABLE_HEADERS = ('Workload', 'E + I units / chunks', 'Slots / ms', 'p (EE, EI, IE, II)', 'w (EE, EI, IE, II)', 'Seed / spread')

def _tuple_text(values):
    return '(' + ', '.join(f'{v:g}' for v in values) + ')'

WORKLOAD_TABLE_ROWS = [
    (w['id'], f"{w['exc_units']:,} + {w['inh_units']:,} / {w['total_chunks']}",
     f"{w['steps']} / {w['duration_ms']:g}",
     _tuple_text(w['probabilities_EE_EI_IE_II']),
     _tuple_text(w['base_weights_EE_EI_IE_II']),
     f"{w['rng_seed']} / {100*w['weight_spread_fraction']:g}%")
    for w in WORKLOADS
]
RETENTION_TABLE_HEADERS = ('Workload', 'Retention / gain setting', 'Input')
RETENTION_TABLE_ROWS = [(w['id'], w['retention'], w['input']) for w in WORKLOADS]
