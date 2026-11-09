#!/usr/bin/env python3
"""Independently validate the post-hoc input/readout analysis against raw arrays.

This validator does not import the analyzer. Temporal bins are assigned by
integer labels, rather than prefix-sum edges. Exponential spike distances are
computed by a dense temporal Gram matrix and the full-tail Toeplitz kernel,
rather than recursive filtering. It adds no simulation or statistical claims.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np


PROBES = ("tonic", "global_burst", "focal_burst")
WIDTHS = (1, 2, 10, 50, 300)
TAUS = (0.1, 0.2, 1.0, 5.0, 30.0)
READOUTS = ("identified", "EI", "global")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def close(observed, expected, label):
    require(math.isclose(float(observed), float(expected), rel_tol=2e-10,
                         abs_tol=1e-9), f"{label}: {observed} != {expected}")


def check_fields(row, expected, label):
    for key, value in expected.items():
        actual = row[key]
        if value is None:
            require(actual in ("", None), f"{label}/{key}: undefined ratio")
        elif isinstance(value, bool):
            require(str(actual).lower() == str(value).lower(), f"{label}/{key}")
        elif isinstance(value, (int, np.integer)):
            require(int(actual) == int(value), f"{label}/{key}: {actual} != {value}")
        elif isinstance(value, (float, np.floating)):
            close(actual, value, f"{label}/{key}")
        else:
            require(actual == value, f"{label}/{key}")


def read_state(path):
    with np.load(path, allow_pickle=False) as data:
        state = data["state_bits"]
    require(state.shape == (300, 125, 10), f"state shape: {path}")
    require(state.dtype == np.uint32, f"state dtype: {path}")
    require(np.isin(state[:, :, 0], (0, 100)).all(), f"chunk synchrony counts: {path}")
    return state


def bin_by_labels(delta, width, offset):
    # Including negative first labels retains every beginning/end sample.
    labels = (np.arange(len(delta)) - offset) // width
    _, inverse = np.unique(labels, return_inverse=True)
    aggregate = np.zeros((inverse.max() + 1, delta.shape[1]), dtype=np.int64)
    np.add.at(aggregate, inverse, delta)
    require(np.array_equal(aggregate.sum(axis=0), delta.sum(axis=0)),
            "all slots must survive shifted binning")
    return aggregate


def readout_numbers(binned):
    e = binned[:, :100].sum(axis=1)
    i = binned[:, 100:].sum(axis=1)
    return (int(np.abs(binned).sum()),
            int(np.abs(e).sum() + np.abs(i).sum()),
            int(np.abs(e + i).sum()))


def summary(values):
    a = np.asarray(values, dtype=float)
    return {"n": len(a), "median": float(np.median(a)),
            "minimum": float(a.min()), "maximum": float(a.max())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sensitivity-dir", type=Path, required=True)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, out = args.sensitivity_dir.resolve(), args.analysis_dir.resolve()
    manifest = load(out / "input-sha256.json")
    inputs = manifest["sensitivity_inputs"]
    analysis_sources = Path(__file__).resolve().parent / "evidence/input-readout"
    for relative, expected in manifest["analysis_sources"].items():
        require(sha(analysis_sources / relative) == expected, f"analysis source hash: {relative}")
    for relative, expected in inputs.items():
        target = (root / relative).resolve()
        require(target.is_relative_to(root), "input hash path escapes sensitivity directory")
        require(sha(target) == expected, f"input hash: {relative}")

    originals = {p: read_state(root / "runs" / f"original__{p}.npz") for p in PROBES}
    for probe, state in originals.items():
        archived = read_state(root / "legacy/runs" /
                              f"homogeneous__original__{probe}__explicit.npz")
        require(np.array_equal(state, archived), f"ten-field baseline bridge: {probe}")
    audits = {r["graph"]: r for r in load(root / "graph-audit.json") if r["type"] == "swap"}
    composed = rows(out / "error-composition.csv")
    require(len(composed) == 114, "114 independent raw-array comparisons expected")
    require(len({r["stem"] for r in composed}) == 114, "duplicate comparison")
    switching = {r["stem"]: r for r in rows(out / "input-switching.csv")}
    require(len(switching) == 57, "57 input-switching rows expected")
    smooth = {(r["stem"], float(r["tau_ms"])): r for r in rows(out / "smooth-values.csv")}
    require(len(smooth) == 570, "570 smoothing rows expected")
    bin_rows = rows(out / "binning-values.csv")
    require(len(bin_rows) == 114 * sum(WIDTHS) * 3, "complete width/offset/readout grid")
    bins = {(r["stem"], int(r["width_slots"]), int(r["offset_slots"]), r["readout"]): r
            for r in bin_rows}
    require(len(bins) == len(bin_rows), "no duplicated width/offset/readout grid rows")

    categories = Counter()
    same_by_seed = defaultdict(list)
    measured = []
    checked_partitions = checked_values = 0
    max_quadratic_error = 0.0
    lag = np.abs(np.arange(300)[:, None] - np.arange(300)[None, :]) * 0.1
    kernels = {tau: np.exp(-lag / tau) for tau in TAUS}
    representative_offsets = {w: sorted(set((0, 1, w // 2, w - 1))) for w in WIDTHS}
    representative_offsets[1] = [0]
    representative_offsets[10] = list(range(10))

    for row in composed:
        stem, group, probe = row["stem"], row["group"], row["probe"]
        require(group in ("swap", "extensive") and probe in PROBES, "comparison identity")
        path = root / ("runs" if group == "swap" else "legacy/runs") / f"{stem}.npz"
        candidate, reference = read_state(path), originals[probe]
        delta = candidate[:, :, 0].astype(np.int64) - reference[:, :, 0].astype(np.int64)
        total = int(reference[:, :, 0].sum())
        slot = int(np.abs(delta).sum())
        node_totals = delta.sum(axis=0)
        count = int(np.abs(node_totals).sum())
        global_count = abs(int(node_totals.sum()))
        one_ms = readout_numbers(bin_by_labels(delta, 10, 0))[0]
        positive, negative = np.maximum(delta, 0).sum(axis=0), np.maximum(-delta, 0).sum(axis=0)
        temporal = int(2 * np.minimum(positive, negative).sum())
        spatial = int(2 * min(node_totals[node_totals > 0].sum(),
                              -node_totals[node_totals < 0].sum()))
        require(temporal + count == slot and spatial + global_count == count,
                f"signed discrepancy identities: {stem}")
        result = {"reference_spikes": total, "Dslot": slot, "Dcount": count,
                  "Dglobal": global_count, "D1ms": one_ms,
                  "Dslot_relative": slot / total, "Dcount_relative": count / total,
                  "Dglobal_relative": global_count / total, "D1ms_relative": one_ms / total,
                  "temporal_cancelled": temporal, "spatial_cancelled_after_time": spatial,
                  "count_retained_fraction": count / slot if slot else None,
                  "temporal_cancelled_fraction": temporal / slot if slot else None,
                  "spatial_cancelled_fraction": spatial / slot if slot else None,
                  "global_retained_fraction": global_count / slot if slot else None}
        check_fields(row, result, stem)
        measured.append({**result, "probe": probe, "group": group})
        if group == "swap":
            seed = int(row["seed"])
            audit = audits[f"swap{seed}"]
            source_delta = reference[:298, int(audit["a"]), 0].astype(np.int64) - reference[:298, int(audit["c"]), 0].astype(np.int64)
            same_input = not np.any(source_delta)
            same_state = np.array_equal(candidate, reference)
            if same_input:
                require(same_state and slot == 0, f"observed null-input agreement: {stem}")
                category = "input_zero_state_equal"
            elif slot == 0:
                category = "input_changed_spikes_equal"
            elif one_ms == 0:
                category = "spikes_changed_1ms_equal"
            else:
                category = "1ms_changed"
            check_fields(switching[stem], {
                "arm": audit["arm"], "source_a": audit["a"], "source_c": audit["c"],
                "target_b": audit["b"], "target_d": audit["d"],
                "shared_input_identical": bool(same_input),
                "all_recorded_bits_equal": bool(same_state), "spikes_identical": slot == 0,
                "bins_1ms_identical": one_ms == 0,
                "spike_mismatch_cells": int(np.count_nonzero(delta)),
                "eligible_source_mismatch_slots": int(np.count_nonzero(source_delta)),
                "category": category}, stem)
            categories[category] += 1
            same_by_seed[seed].append((probe, slot == 0, category))

        for width in WIDTHS:
            for offset in representative_offsets[width]:
                aggregate = bin_by_labels(delta, width, offset)
                quantities = readout_numbers(aggregate)
                require(global_count <= quantities[2] <= quantities[1] <= quantities[0] <= slot,
                        f"readout contraction: {stem}/{width}/{offset}")
                require(count <= quantities[0], "time-cumulative identified lower bound")
                for readout, value in zip(READOUTS, quantities):
                    check_fields(bins[stem, width, offset, readout], {
                        "l1_numerator": value, "reference_spikes": total,
                        "relative_l1": value / total}, f"bin/{stem}/{width}/{offset}/{readout}")
                    checked_values += 1
                checked_partitions += 1

        # Temporal Gram yields a different implementation of the exact integral
        # over the complete causal exponential tail after the last observed event.
        representatives = delta.astype(float) / 100.0
        gram = representatives @ representatives.T
        for tau, kernel in kernels.items():
            expected = float(np.sum(gram * kernel, dtype=np.float64) / 2)
            require(expected >= -1e-9, "positive exponential kernel quadratic")
            expected = max(0.0, expected)
            actual = smooth[stem, tau]
            max_quadratic_error = max(max_quadratic_error, abs(float(actual["vr_squared"]) - expected))
            check_fields(actual, {"vr_squared": expected,
                                  "reference_representative_spikes": total // 100,
                                  "normalized_squared_distance": 2 * expected / (total / 100)},
                         f"smooth/{stem}/{tau}")

    patterns = Counter()
    pattern_rows = {int(r["seed"]): r for r in rows(out / "graph-input-patterns.csv")}
    require(len(same_by_seed) == len(pattern_rows) == 19, "19 paired graph patterns")
    for seed, graph_results in same_by_seed.items():
        require(len(graph_results) == 3, "three inputs per fixed graph")
        equal = sum(item[1] for item in graph_results)
        pattern = "all_equal" if equal == 3 else "all_different" if equal == 0 else "switches"
        check_fields(pattern_rows[seed], {"spike_equal_probe_count": equal, "pattern": pattern,
                     **{f"{probe}_category": category for probe, _, category in graph_results}},
                     f"pattern/{seed}")
        patterns[pattern] += 1

    # Recompute every descriptive aggregate from its complete underlying CSV.
    composition_summary = rows(out / "composition-summary.csv")
    require(len(composition_summary) == 6, "six composition summaries")
    metrics = ("Dslot_relative", "Dcount_relative", "Dglobal_relative", "D1ms_relative",
               "count_retained_fraction", "temporal_cancelled_fraction",
               "spatial_cancelled_fraction", "global_retained_fraction")
    for row in composition_summary:
        selected = [v for v in measured if v["probe"] == row["probe"] and v["group"] == row["group"]]
        expect = {"n": len(selected), "nonzero_slot_error": sum(v["Dslot"] > 0 for v in selected)}
        for metric in metrics:
            values = [v[metric] for v in selected if v[metric] is not None]
            expect.update({f"{metric}_{k}": v for k, v in summary(values).items()})
        check_fields(row, expect, f"composition summary/{row['probe']}/{row['group']}")

    bin_groups = defaultdict(list)
    for row in bin_rows:
        key = (row["probe"], row["group"], int(row["width_slots"]), int(row["offset_slots"]), row["readout"])
        bin_groups[key].append(float(row["relative_l1"]))
        close(row["relative_l1"], int(row["l1_numerator"]) / int(row["reference_spikes"]), "CSV bin normalization")
    bin_summary = rows(out / "binning-summary.csv")
    require(len(bin_summary) == 3 * 2 * sum(WIDTHS) * 3, "complete bin summary grid")
    for row in bin_summary:
        key = (row["probe"], row["group"], int(row["width_slots"]), int(row["offset_slots"]), row["readout"])
        check_fields(row, summary(bin_groups[key]), f"bin summary/{key}")
    separations = rows(out / "binning-separation.csv")
    require(len(separations) == 3 * len(WIDTHS) * 3, "complete bin separation grid")
    for row in separations:
        probe, width, readout = row["probe"], int(row["width_slots"]), row["readout"]
        margins = [min(bin_groups[probe, "extensive", width, offset, readout]) -
                   max(bin_groups[probe, "swap", width, offset, readout]) for offset in range(width)]
        envelope = min(value for offset in range(width) for value in bin_groups[probe, "extensive", width, offset, readout]) - max(
            value for offset in range(width) for value in bin_groups[probe, "swap", width, offset, readout])
        check_fields(row, {"offsets": width, "strictly_separated_offsets": sum(m > 0 for m in margins),
                           "minimum_margin": min(margins), "maximum_margin": max(margins),
                           "cross_offset_envelope_margin": envelope},
                     f"bin separation/{probe}/{width}/{readout}")

    smooth_groups = defaultdict(list)
    for row in smooth.values():
        smooth_groups[row["probe"], row["group"], float(row["tau_ms"])].append(float(row["normalized_squared_distance"]))
    smooth_summary = rows(out / "smooth-summary.csv")
    require(len(smooth_summary) == 30, "complete smooth summary grid")
    for row in smooth_summary:
        check_fields(row, summary(smooth_groups[row["probe"], row["group"], float(row["tau_ms"])]), "smooth summary")
    smooth_separation = rows(out / "smooth-separation.csv")
    require(len(smooth_separation) == 15, "complete smooth separation grid")
    for row in smooth_separation:
        probe, tau = row["probe"], float(row["tau_ms"])
        lo, hi = min(smooth_groups[probe, "extensive", tau]), max(smooth_groups[probe, "swap", tau])
        check_fields(row, {"extensive_minimum": lo, "swap_maximum": hi,
                           "range_separation": lo - hi, "strictly_separated": lo > hi}, "smooth separation")

    main_summary = load(out / "summary.json")
    require(main_summary["analysis_type"] == "post_hoc" and main_summary["new_simulations"] == 0,
            "analysis must remain explicitly post hoc with no new simulations")
    require(main_summary["category_counts"] == dict(categories), "summary category counts")
    require(main_summary["input_switching_counts"] == dict(patterns), "summary switching counts")
    require(main_summary["original_graphs"] == 1 and main_summary["swaps"] == 19 and
            main_summary["extensive_graphs"] == 19 and main_summary["probes"] == list(PROBES),
            "summary study scope")
    for key, csv_records, identity in (
        ("composition", composition_summary, ("probe", "group")),
        ("binning_separation", separations, ("probe", "width_slots", "readout")),
        ("smooth_summary", smooth_summary, ("probe", "group", "tau_ms")),
        ("smooth_separation", smooth_separation, ("probe", "tau_ms")),
    ):
        json_records = main_summary[key]
        require(len(json_records) == len(csv_records), f"summary/CSV row count: {key}")
        for record in json_records:
            matches = [r for r in csv_records if all(str(r[k]) == str(record[k]) for k in identity)]
            require(len(matches) == 1, f"summary/CSV identity: {key}")
            check_fields(matches[0], record, f"summary/CSV {key}")
    analyzer_validation = load(out / "validation.json")
    output_hashes = analyzer_validation["outputs"]
    for relative, expected in output_hashes.items():
        require(sha(out / relative) == expected, f"analysis output hash: {relative}")
    for relative, expected in inputs.items():
        require(sha(root / relative) == expected, f"input changed during validation: {relative}")
    report = {
        "status": "pass", "analysis_type": "post_hoc", "new_simulations": 0,
        "independent_implementation": True, "analyzer_imported": False,
        "input_hashes_verified": len(inputs), "analysis_source_hashes_verified": len(manifest["analysis_sources"]),
        "original_baseline_bridges_bitwise_equal": 3,
        "raw_comparisons": len(composed), "exact_signed_cancellation_identities": len(composed),
        "switching_cases": 57, "category_counts": dict(categories), "input_switching_counts": dict(patterns),
        "independent_offset_scheme": "integer slot labels with all edge samples retained",
        "independent_offsets_by_width": representative_offsets,
        "raw_array_partitions_checked": checked_partitions, "raw_binned_readout_values_checked": checked_values,
        "all_binning_values_normalization_checked": len(bin_rows),
        "all_binning_summaries_checked": len(bin_summary), "all_binning_separations_checked": len(separations),
        "full_tail_exponential_check": "dense temporal Gram matrix against exponential Toeplitz kernel",
        "raw_full_tail_exponential_distances_checked": len(smooth),
        "maximum_absolute_quadratic_difference": max_quadratic_error,
        "all_smooth_summaries_checked": len(smooth_summary), "all_smooth_separations_checked": len(smooth_separation),
        "analysis_output_hashes_verified": len(output_hashes),
        "scope": "Numerical claims and recorded inputs; analytical proof and generalization remain separate.",
        "validator_sha256": sha(__file__), "source_input_manifest_sha256": sha(out / "input-sha256.json"),
        "source_summary_sha256": sha(out / "summary.json"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "pass", "raw_comparisons": len(composed),
                      "raw_full_tail_exponential_distances_checked": len(smooth),
                      "report": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
