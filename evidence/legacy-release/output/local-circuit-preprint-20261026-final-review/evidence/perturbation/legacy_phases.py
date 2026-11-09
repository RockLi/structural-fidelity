#!/usr/bin/env python3
"""Read-only phased diagnostics of the 48 archived explicit trajectories.

These are post-step model states, not a biological voltage calibration.  The
fixed rank-five basis is a reference *linear subspace*, not a learned manifold.
No simulation, fitting, graph selection, or source modification occurs here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


PHASES = (("conditioning", 0, 80), ("early_recovery", 80, 150),
          ("late_recovery", 150, 300))
PROBES = ("module_burst", "shifted_burst", "focal_burst")
CHANNELS = ("V", "gE", "gI")
STATUS = {0: "dormant", 1: "active", 2: "pending_wake_up"}
STEPS, CHUNKS, WIDTH, DT_MS = 300, 125, 10, 0.1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def describe(values) -> dict:
    x = np.asarray(values, dtype=np.float64)
    return {"n": int(x.size), "min": float(x.min()),
            "median": float(np.median(x)), "max": float(x.max())}


def distribution(values) -> dict:
    x = np.asarray(values, dtype=np.float64)
    q = np.quantile(x, [0, .01, .05, .25, .5, .75, .95, .99, 1])
    keys = ("min", "q01", "q05", "q25", "median", "q75", "q95", "q99", "max")
    return {**{k: float(v) for k, v in zip(keys, q)},
            "mean": float(x.mean()), "sd": float(x.std()),
            "rms": float(np.sqrt(np.mean(x*x)))}


def read_run(npz: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with np.load(npz, allow_pickle=False) as z:
        assert z.files == ["state_bits"], (npz, z.files)
        bits = z["state_bits"]
    assert bits.shape == (STEPS, CHUNKS, WIDTH) and bits.dtype == np.uint32, npz
    state = np.ascontiguousarray(bits[:, :, 1:4]).view(np.float32).astype(np.float64)
    all_float = np.ascontiguousarray(bits[:, :, 1:8]).view(np.float32)
    assert np.isfinite(all_float).all(), npz
    assert set(np.unique(bits[:, :, 0])).issubset({0, 100}), npz
    assert set(np.unique(bits[:, :, 9])).issubset(STATUS), npz
    counts = np.loadtxt(npz.with_suffix(".csv"), delimiter=",", skiprows=1,
                        dtype=np.int64)
    assert counts.shape == (STEPS, 5), npz
    assert np.array_equal(counts[:, 0], np.arange(STEPS)), npz
    assert np.array_equal(counts[:, 1], bits[:, :, 0].sum(axis=1)), npz
    return bits, state, counts


def gates(bits: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # refractory_until was recorded after the update.  The kernel tests the
    # value that existed before the step; a spike sets the POST value to t+2.
    post_until = bits[:, :, 8].astype(np.int64)
    pre_until = np.zeros_like(post_until)
    pre_until[1:] = post_until[:-1]
    step = np.arange(STEPS)[:, None]
    before_gate = pre_until > step
    mistaken_after_gate = post_until > step
    fired = bits[:, :, 0] > 0
    previous_fired = np.zeros_like(fired)
    previous_fired[1:] = fired[:-1]
    assert np.array_equal(before_gate, previous_fired)
    assert not np.any(before_gate & fired)
    assert np.array_equal(mistaken_after_gate, before_gate | fired)
    assert np.all(post_until[fired] == np.broadcast_to(step + 2, fired.shape)[fired])
    assert np.array_equal(post_until[~fired], pre_until[~fired])
    return before_gate, mistaken_after_gate


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--output", type=Path,
                    help="New/empty output directory; default ROOT/legacy_diagnostics")
    args = ap.parse_args()
    root = args.root.resolve()
    inputs = root / "legacy_inputs"
    out = args.output.resolve() if args.output else root / "legacy_diagnostics"
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"Refusing to overwrite a nonempty diagnostic directory: {out}")
    paths = sorted((inputs / "runs").glob("*__explicit.npz"))
    assert len(paths) == 48, f"Expected 48 explicit archives, got {len(paths)}"
    assert len(list((inputs / "runs").glob("*__explicit.csv"))) == 48
    protocol_path = inputs / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert (protocol["steps"], protocol["chunks"], protocol["units_per_chunk"],
            protocol["dt_ms"]) == (STEPS, CHUNKS, 100, DT_MS)
    basis_path = inputs / "reference-subspace-basis.npz"
    with np.load(basis_path, allow_pickle=False) as z:
        basis, common_scale = z["basis"], z["channel_scale"]
        assert z["mean"].shape == (375,)
    assert basis.shape == (375, 5) and common_scale.shape == (3,)
    assert np.isfinite(basis).all() and np.all(common_scale > 0)
    assert np.allclose(basis.T @ basis, np.eye(5), rtol=0, atol=1e-12)
    payloads, source_hashes = {}, {}
    for path in paths:
        graph, probe, mode = path.stem.split("__")
        assert probe in PROBES and mode == "explicit", path
        payloads[graph, probe] = read_run(path)
        for p in (path, path.with_suffix(".csv")):
            source_hashes[str(p.relative_to(root))] = sha(p)
    graphs = sorted({g for g, _ in payloads})
    assert len(graphs) == 16 and "original" in graphs
    assert all((g, p) in payloads for g in graphs for p in PROBES)
    for p in (basis_path, protocol_path):
        source_hashes[str(p.relative_to(root))] = sha(p)
    references = {p: payloads["original", p][1] for p in PROBES}
    scales = {p: x.std(axis=(0, 1)) for p, x in references.items()}
    assert all(np.all(s > 1e-8) for s in scales.values())
    assert np.allclose(common_scale, scales["module_burst"], rtol=0, atol=1e-10)
    rows, variable_rows, status_rows = [], [], []
    for graph in graphs:
        for probe in PROBES:
            bits, state, count_csv = payloads[graph, probe]
            reference = references[probe]
            delta = state - reference
            normalized = delta / scales[probe]
            common = (delta / common_scale).reshape(STEPS, -1)
            in_coefficients = common @ basis
            outside = common - in_coefficients @ basis.T
            before_gate, mistaken_after_gate = gates(bits)
            for phase, start, stop in PHASES:
                sl = slice(start, stop)
                key = dict(graph=graph,
                           treatment="original" if graph == "original" else graph.rsplit("_", 1)[0],
                           probe=probe, phase=phase, start_slot=start, stop_slot_exclusive=stop,
                           start_ms=start*DT_MS, stop_ms_exclusive=stop*DT_MS)
                mse = float(np.mean(common[sl]**2))
                # The coefficient and residual energies use one common
                # denominator (time slots * 375), never 5 versus 375 features.
                divisor = (stop-start)*375
                inside_mse = float(np.sum(in_coefficients[sl]**2)/divisor)
                outside_mse = float(np.sum(outside[sl]**2)/divisor)
                assert np.isclose(mse, inside_mse+outside_mse, rtol=1e-12, atol=1e-12)
                imbalance = state[sl, :, 1]-state[sl, :, 2]
                ref_imbalance = reference[sl, :, 1]-reference[sl, :, 2]
                norm_imbalance = imbalance/(state[sl, :, 1]+state[sl, :, 2]+1e-12)
                row = dict(**key,
                           state_score=float(np.sqrt(np.mean(normalized[sl]**2))),
                           terminal_state_score=float(np.sqrt(np.mean(normalized[stop-1]**2))),
                           raw_state_rmse=float(np.sqrt(np.mean(delta[sl]**2))),
                           common_scale_state_mse=mse,
                           common_scale_rank5_inside_mse=inside_mse,
                           common_scale_rank5_outside_mse=outside_mse,
                           common_scale_rank5_outside_energy_fraction=outside_mse/mse if mse > 0 else None,
                           refractory_pre_gate_fraction=float(before_gate[sl].mean()),
                           incorrect_post_until_gate_fraction=float(mistaken_after_gate[sl].mean()),
                           post_until_overcount_fraction=float((mistaken_after_gate[sl]&~before_gate[sl]).mean()),
                           firing_chunk_slot_fraction=float((bits[sl, :, 0]>0).mean()),
                           total_spikes=int(bits[sl, :, 0].sum()),
                           csv_active_chunks_mean=float(count_csv[sl, 4].mean()),
                           imbalance_mean=float(imbalance.mean()),
                           imbalance_rms=float(np.sqrt(np.mean(imbalance**2))),
                           imbalance_delta_rmse=float(np.sqrt(np.mean((imbalance-ref_imbalance)**2))),
                           imbalance_negative_fraction=float((imbalance<0).mean()),
                           signed_normalized_imbalance_mean=float(norm_imbalance.mean()),
                           absolute_normalized_imbalance_mean=float(np.abs(norm_imbalance).mean()))
                for ci, channel in enumerate(CHANNELS):
                    row[channel+"_rmse"] = float(np.sqrt(np.mean(delta[sl, :, ci]**2)))
                    row[channel+"_reference_full_run_sd"] = float(scales[probe][ci])
                    variable_rows.append(dict(**key, variable=channel,
                                              **distribution(state[sl, :, ci])))
                variable_rows.append(dict(**key, variable="gE_minus_gI",
                                          **distribution(imbalance)))
                rows.append(row)
                status = bits[:, :, 9]
                sr = dict(**key, post_status_is_execution_flag=False)
                for code, label in STATUS.items():
                    sr["phase_post_"+label+"_fraction"] = float((status[sl]==code).mean())
                    sr["terminal_post_"+label+"_chunks"] = int(np.sum(status[stop-1]==code))
                assert sum(sr["terminal_post_"+label+"_chunks"] for label in STATUS.values()) == CHUNKS
                status_rows.append(sr)
    assert len(rows) == len(status_rows) == 144 and len(variable_rows) == 576
    summary_metrics = ("state_score", "terminal_state_score", "V_rmse", "gE_rmse", "gI_rmse",
                       "common_scale_rank5_outside_energy_fraction", "refractory_pre_gate_fraction",
                       "incorrect_post_until_gate_fraction", "imbalance_mean")
    group_summary = {}
    for probe in PROBES:
        group_summary[probe] = {}
        for phase, _, _ in PHASES:
            group_summary[probe][phase] = {}
            for treatment in ("A_degree", "B_aligned", "C_random"):
                selected = [r for r in rows if (r["probe"], r["phase"], r["treatment"]) ==
                            (probe, phase, treatment)]
                assert len(selected) == 5
                group_summary[probe][phase][treatment] = {
                    metric: describe([r[metric] for r in selected]) for metric in summary_metrics}
    summary = {
        "status": "pass", "conditions": 48, "graphs": 16, "probes": list(PROBES),
        "phase_rows": len(rows), "variable_distribution_rows": len(variable_rows),
        "phase_definitions": [{"phase": p, "start_slot": a, "stop_slot_exclusive": b}
                              for p, a, b in PHASES],
        "phase_state_error_scaling": "Each probe uses the SD across all 300 slots and all 125 chunks of its original explicit reference, separately for V, gE, gI; unchanged across phases and graphs.",
        "rank5_scaling": "The archived rank-five basis and three channel scales from original/module_burst are fixed for every probe and phase. Difference energies share denominator phase_slots*375; centering cancels in graph-minus-reference differences.",
        "rank5_common_channel_scale": dict(zip(CHANNELS, map(float, common_scale))),
        "refractory_definition": "pre_until[0]=0; pre_until[t]=post_until[t-1]; gate[t]=(pre_until[t]>t). The post-update test overcounts newly spiking cells, which integrated before setting until=t+2.",
        "refractory_verification": {"runs_checked": 48,
                                   "pre_gate_equals_previous_slot_spike_all_cells": True,
                                   "post_gate_equals_pre_gate_or_current_spike_all_cells": True,
                                   "gated_current_spikes": 0,
                                   "post_until_changed_only_when_fired": True},
        "execution_limit": "Post-step chunk status is not a record of whether the kernel ran. Here a reconstructed refractory gate follows a previous-slot spike and that chunk is scheduled; the archived payload cannot reconstruct every other stepped/dormant event. No decay exposure or complete update count is inferred from post status.",
        "count_verification": {"npz_population_counts_equal_csv_all_runs": True,
                               "within_chunk_counts_are_zero_or_100": True},
        "scope": ["Post-step model coordinates; no claim of calibrated biological mV or conductance units.",
                  "Reference linear subspace outside-error is not distance from a nonlinear manifold.",
                  "One original graph, 15 dependent conditional rewires; summaries are descriptive, not independent population estimates.",
                  "Phase endpoints label archived post-step samples; the conditioning drive is present on slots 0 through 79.",
                  "No complete stepped mask exists in these old archives; status distributions remain explicitly post-step."],
        "group_phase_metrics": group_summary,
        "pooled_rewired_phase_metrics": {
            p: {metric: describe([r[metric] for r in rows if r["phase"] == p and r["graph"] != "original"])
                for metric in summary_metrics} for p, _, _ in PHASES},
        "global_state_ranges": {ch: {"min": min(r["min"] for r in variable_rows if r["variable"] == ch),
                                     "max": max(r["max"] for r in variable_rows if r["variable"] == ch)}
                                for ch in (*CHANNELS, "gE_minus_gI")},
        "full_trajectory_refractory_gate_fraction": float(np.mean([gates(x[0])[0].mean() for x in payloads.values()])),
        "full_trajectory_incorrect_post_gate_fraction": float(np.mean([gates(x[0])[1].mean() for x in payloads.values()])),
        "inputs_sha256": source_hashes,
        "script_sha256": sha(Path(__file__).resolve()),
    }
    # Outputs are created only after every input and calculation has passed.
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "phase-state-errors.csv", rows)
    write_csv(out / "phase-variable-distributions.csv", variable_rows)
    write_csv(out / "phase-post-status.csv", status_rows)
    assert all(sha(root / name) == digest for name, digest in source_hashes.items())
    summary["outputs_sha256"] = {p.name: sha(p) for p in sorted(out.glob("*.csv"))}
    write_json(out / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "conditions", "phase_rows", "global_state_ranges",
                     "full_trajectory_refractory_gate_fraction", "full_trajectory_incorrect_post_gate_fraction")}, indent=2))


if __name__ == "__main__":
    main()
