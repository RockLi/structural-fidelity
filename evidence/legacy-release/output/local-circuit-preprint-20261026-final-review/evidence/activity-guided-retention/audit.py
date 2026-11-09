#!/usr/bin/env python3
"""Independent audit of the prospectively locked activity-guided study.

No study/analyzer helpers are imported. Scores use independently constructed
input increments; the exponential spike distance uses a dense Toeplitz kernel.
The audit checks recorded evidence and hashes, not historical access control.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

N, STEPS, UNITS, EMISSIONS = 125, 300, 100, 298
PROBES = ("train", "spatial", "temporal", "spatiotemporal")
POLICIES = ("random", "mean", "coactivity", "shuffled")
ARM_BUDGETS = (146, 60, 64, 12)
CHECKS: Counter = Counter()


def check(condition, label, detail=""):
    if not bool(condition):
        raise AssertionError(f"{label}: {detail}")
    CHECKS[label] += 1


def close(actual, expected, label, rtol=2e-9, atol=2e-10):
    if expected is None:
        check(actual in (None, "", "null"), label, (actual, expected))
    else:
        check(actual not in (None, "", "null"), label, (actual, expected))
        check(math.isfinite(float(actual)) and math.isclose(float(actual), float(expected),
              rel_tol=rtol, abs_tol=atol), label, (actual, expected))


def js(path):
    return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def locked(root, name):
    lock = js(root / name)
    check(isinstance(lock.get("files"), dict) and bool(lock["files"]), "nonempty_lock", name)
    for rel, digest in lock["files"].items():
        p = (root / rel).resolve()
        check(p.is_relative_to(root.resolve()), "lock_path_inside_study", rel)
        check(p.is_file() and sha(p) == digest, "locked_file_hash", rel)
    when = datetime.fromisoformat(lock["locked_utc"].replace("Z", "+00:00"))
    check(when.tzinfo is not None, "lock_timezone", name)
    return lock, when


def graph(path):
    rr = rows(path)
    check(bool(rr) and set(rr[0]) == {"arm", "source", "target", "weight_bits", "delay"},
          "graph_schema", str(path))
    a = np.array([[int(r[k]) for k in ("arm", "source", "target", "weight_bits", "delay")]
                  for r in rr], dtype=np.int64)
    check(len(a) == 2845, "graph_edge_count", str(path))
    check(np.all((a[:, 1:3] >= 0) & (a[:, 1:3] < N)), "graph_node_range", str(path))
    check(np.all(a[:, 1] != a[:, 2]), "graph_no_self_loops", str(path))
    check(len(set(map(tuple, a[:, 1:3]))) == len(a), "graph_no_duplicate_pairs", str(path))
    check(np.array_equal(a[:, 0], 2 * (a[:, 1] >= 100) + (a[:, 2] >= 100)),
          "graph_correct_arms", str(path))
    check(np.all(a[:, 4] == 1), "graph_delays", str(path))
    weights = a[:, 3].astype(np.uint32).view(np.float32)
    check(np.isfinite(weights).all() and (weights > 0).all(), "graph_weights_positive_finite", str(path))
    return a


def graph_invariants(original, candidate, label):
    check(np.array_equal(original[:, (0, 1, 3, 4)], candidate[:, (0, 1, 3, 4)]),
          "row_source_arm_weight_delay_preserved", label)
    # Exact per-node, per-arm multisets jointly preserve degrees, weights,
    # delays, and strengths without relying on floating-point sums.
    for col, name in ((1, "out"), (2, "in")):
        key_cols = (0, col, 3, 4)
        check(Counter(map(tuple, original[:, key_cols])) == Counter(map(tuple, candidate[:, key_cols])),
              "per_node_arm_" + name + "_weight_delay_multiset", label)
    orig_pairs = set(map(tuple, original[:, 1:3]))
    for arm, budget in enumerate(ARM_BUDGETS):
        a, b = original[original[:, 0] == arm], candidate[candidate[:, 0] == arm]
        missing = set(map(tuple, a[:, 1:3])) - set(map(tuple, b[:, 1:3]))
        added = set(map(tuple, b[:, 1:3])) - set(map(tuple, a[:, 1:3]))
        check(len(missing) == len(added) == budget, "exact_arm_adjacency_budget", (label, arm))
        changed = b[:, 2] != a[:, 2]
        check(int(changed.sum()) == budget, "exact_arm_changed_row_budget", (label, arm))
        check(all(tuple(pair) not in orig_pairs for pair in b[changed, 1:3]),
              "changed_rows_never_restore_original_pair", (label, arm))


def weights_by_channel(a):
    w = np.zeros((2, N, N), dtype=np.float64)
    weights = a[:, 3].astype(np.uint32).view(np.float32).astype(np.float64)
    for (arm, source, target, _, _), value in zip(a, weights):
        w[int(arm >= 2), target, source] = value
    return w


def direct_input_difference(original, candidate, source):
    # Accumulate changed edges directly rather than using a covariance trace.
    d = np.zeros((2, N, source.shape[1]), dtype=np.float64)
    changed = np.flatnonzero(original[:, 2] != candidate[:, 2])
    for idx in changed:
        arm, src, old_target, bits, _ = original[idx]
        new_target = candidate[idx, 2]
        weight = np.array([bits], dtype=np.uint32).view(np.float32)[0].item()
        signal = weight * source[src]
        d[int(arm >= 2), old_target] -= signal
        d[int(arm >= 2), new_target] += signal
    return d


def sparse_quadratic(delta, gram):
    # Evaluate target-by-target using only nonzero source columns.
    total = 0.0
    for channel in delta:
        for row in channel:
            ix = np.flatnonzero(row)
            if len(ix):
                v = row[ix]
                total += float(v @ gram[np.ix_(ix, ix)] @ v)
    return total


def score_terms(original, candidate, source, shuffle_gram):
    delta = weights_by_channel(candidate) - weights_by_channel(original)
    input_difference = direct_input_difference(original, candidate, source)
    mean_difference = input_difference.mean(axis=2)
    length = source.shape[1]
    mean = length * float(np.square(mean_difference).sum())
    coactivity = float(np.square(input_difference).sum())
    centered = source - source.mean(axis=1, keepdims=True)
    diagonal = np.square(centered).sum(axis=1)
    expected_shuffle = mean + float((np.square(delta).sum(axis=(0, 1)) * diagonal).sum())
    shuffled = sparse_quadratic(delta, shuffle_gram)
    # Algebraic check: common time permutation preserves the score.
    check(math.isclose(float(np.square(input_difference[:, :, ::-1]).sum()), coactivity,
                       rel_tol=1e-13, abs_tol=1e-10), "common_time_permutation_invariance")
    centered_part = float(np.square(input_difference - mean_difference[:, :, None]).sum())
    close(coactivity, mean + centered_part, "mean_centered_score_decomposition", rtol=1e-12)
    check(coactivity + 1e-9 >= mean, "coactivity_score_at_least_mean")
    return {"J_mean": mean, "J_coactivity": coactivity,
            "J_shuffled": shuffled, "J_shuffle_expectation": expected_shuffle}


def state(path):
    with np.load(path, allow_pickle=False) as z:
        check(z.files == ["state_bits"], "state_npz_schema", str(path))
        a = z["state_bits"]
    check(a.shape == (STEPS, N, 10) and a.dtype == np.uint32, "state_dimensions_dtype", str(path))
    check(np.all((a[:, :, 0] == 0) | (a[:, :, 0] == 100)), "synchronized_chunk_spikes", str(path))
    for field in range(1, 8):
        check(np.isfinite(a[:, :, field].copy().view(np.float32)).all(), "finite_observed_state", (str(path), field))
    check(np.isin(a[:, :, 9], [0, 1, 2]).all(), "valid_status_codes", str(path))
    return a


def metrics(reference, candidate):
    r = reference[:, :, 0].astype(np.int64)
    c = candidate[:, :, 0].astype(np.int64)
    d = c - r
    total = int(r.sum())
    dslot = int(np.abs(d).sum())
    d1ms = int(np.abs(d.reshape(30, 10, N).sum(axis=1)).sum())
    dcount = int(np.abs(d.sum(axis=0)).sum())
    dglobal = abs(int(d.sum()))
    dpopulation = int(np.abs(d.sum(axis=1)).sum())
    check(dcount <= d1ms <= dslot, "temporal_aggregation_L1_bounds")
    check(dglobal <= dslot, "spatial_aggregation_L1_bound")
    # Independent complete exponential-tail formula, dt=.1 ms, tau=1 ms.
    representative_delta = d.astype(np.float64) / UNITS
    distance = np.abs(np.arange(STEPS)[:, None] - np.arange(STEPS)[None, :])
    kernel = np.exp(-0.1 * distance)
    gram = representative_delta @ representative_delta.T
    quadratic = float((gram * kernel).sum())
    check(quadratic >= -1e-9, "nonnegative_exponential_distance")
    fields = (1, 2, 3)
    rr = np.stack([reference[:, :, f].copy().view(np.float32).astype(np.float64) for f in fields], axis=-1)
    cc = np.stack([candidate[:, :, f].copy().view(np.float32).astype(np.float64) for f in fields], axis=-1)
    difference = cc - rr
    scales = rr.std(axis=(0, 1), ddof=0)
    abs_rms = np.sqrt(np.square(difference).mean(axis=(0, 1)))
    standardized = float(np.sqrt(np.square(difference / scales).mean())) if (scales > 0).all() else None
    changed_slots = np.flatnonzero(np.any(d != 0, axis=1))
    first = int(changed_slots[0]) if len(changed_slots) else None
    return {"reference_spikes": total, "candidate_spikes": int(c.sum()),
            "Dslot": dslot, "D1ms": d1ms, "Dcount": dcount,
            "Dglobal_cumulative": dglobal, "Dpopulation_slot": dpopulation,
            "raw_slot_l1": dslot / total if total else None,
            "bin1ms_l1": d1ms / total if total else None,
            "cumulative_l1": dcount / total if total else None,
            "Rcount": dcount / dslot if dslot else None,
            "van_rossum_tau1": max(0.0, quadratic) / (total / UNITS) if total else None,
            "state_rms_standardized": standardized,
            "voltage_rms_abs": float(abs_rms[0]), "exc_rms_abs": float(abs_rms[1]),
            "inh_rms_abs": float(abs_rms[2]), "spike_mismatch_cells": int(np.count_nonzero(d)),
            "spikes_identical": dslot == 0, "first_spike_divergence_slot": first,
            "first_spike_divergence_ms": (first + 1) * 0.1 if first is not None else None,
            "recorded_bits_equal": bool(np.array_equal(reference, candidate))}


def validate_events(root):
    result = {}
    amplitude = int(np.array([150], dtype=np.float32).view(np.uint32)[0])
    for probe in PROBES:
        rr = rows(root / "events" / (probe + ".csv"))
        check(bool(rr) and set(rr[0]) == {"slot", "target", "amplitude_bits"}, "events_schema", probe)
        events = [tuple(int(r[k]) for k in ("slot", "target", "amplitude_bits")) for r in rr]
        check(events == sorted(events) and len(set((t, j) for t, j, b in events)) == len(events),
              "events_canonical_unique", probe)
        check(len(events) == 1600 and all(b == amplitude for t, j, b in events), "events_equal_dose", probe)
        targets = sorted({j for t, j, b in events})
        slots = sorted({t for t, j, b in events})
        expected_slots = list(range(80)) if probe in ("train", "spatial") else list(range(40)) + list(range(80, 120))
        check(len(targets) == 20 and all(0 <= j < 100 for j in targets), "events_twenty_E_targets", probe)
        check(slots == expected_slots, "events_prespecified_slots", probe)
        check(events == [(t, j, amplitude) for t in slots for j in targets], "events_full_cartesian_input", probe)
        result[probe] = targets
    check(result["train"] == result["temporal"] == list(range(0, 100, 5)), "original_input_mask")
    check(result["spatial"] == result["spatiotemporal"] != result["train"], "heldout_shared_new_mask")
    return {"new_mask": result["spatial"], "training_mask_overlap": len(set(result["train"]) & set(result["spatial"]))}


def independent_candidate(original, seed):
    """Replay the published seed/algorithm, independently of study.py."""
    rng = random.Random(seed)
    out = original.copy()
    initial = {tuple(x) for x in original[:, 1:3]}
    occupied = set(initial)
    proposal_counts = []
    for arm, budget in enumerate(ARM_BUDGETS):
        remaining = [i for i, row in enumerate(original) if row[0] == arm]
        moved = 0
        for proposals in range(1, 200001):
            i, j = rng.sample(remaining, 2)
            u, v = map(int, out[i, 1:3])
            x, y = map(int, out[j, 1:3])
            proposed = ((u, y), (x, v))
            if u == x or v == y or u == y or x == v:
                continue
            if any(pair in initial or pair in occupied for pair in proposed):
                continue
            if tuple(out[i, 3:5]) != tuple(out[j, 3:5]):
                continue
            occupied.difference_update(((u, v), (x, y)))
            occupied.update(proposed)
            out[i, 2], out[j, 2] = y, v
            remaining = [k for k in remaining if k not in (i, j)]
            moved += 2
            if moved == budget:
                break
        check(moved == budget, "candidate_fixed_cap_success", (seed, arm))
        proposal_counts.append(proposals)
    return out, proposal_counts


def audit_selection(root, protocol, original, training, design_time):
    selection_lock, selection_time = locked(root, "selection-lock.json")
    check(selection_time >= design_time, "selection_after_design")
    check(selection_lock.get("scientific_runs_started") is False, "selection_before_runs")
    check(np.array_equal(graph(root / "graphs/original.csv"), original), "unchanged_original_graph")
    candidates = rows(root / "candidates.csv")
    check(len(candidates) == 640, "candidate_count")
    indexed = {(int(r["block"]), int(r["candidate"])): r for r in candidates}
    check(set(indexed) == {(b, k) for b in range(10) for k in range(64)}, "complete_unique_candidate_grid")
    aliases = js(root / "graph-aliases.json")
    assertions = {r["graph"]: r for r in js(root / "graph-audit.json")}
    check(len(assertions) == 640, "graph_audit_record_count")
    source = training[:EMISSIONS, :, 0].T.astype(np.float64) / UNITS
    first_hash = {}
    reconstructed_aliases = {}
    max_score_error = Counter()
    for block in range(10):
        generator = np.random.Generator(np.random.PCG64(1000000 + block))
        gram = np.zeros((N, N), dtype=np.float64)
        for repeat in range(32):
            shuffled = np.empty_like(source)
            for j in range(N):
                permutation = generator.permutation(EMISSIONS)
                shuffled[j] = source[j, permutation]
                check(np.array_equal(np.sort(shuffled[j]), np.sort(source[j])), "shuffle_source_multiset")
            gram += shuffled @ shuffled.T / 32
        for index in range(64):
            row = indexed[(block, index)]
            name = f"b{block:02d}_c{index:02d}"
            seed = 980000 + 1000 * block + index
            check(row["graph"] == name and int(row["seed"]) == seed, "candidate_name_seed", name)
            candidate = graph(root / "graphs" / f"{name}.csv")
            graph_invariants(original, candidate, name)
            regenerated, proposals = independent_candidate(original, seed)
            check(np.array_equal(candidate, regenerated), "candidate_seed_reconstruction", name)
            stated = assertions[name]
            check([x["proposals"] for x in stated["swaps"]] == proposals, "candidate_proposal_count", name)
            check(stated["removed_by_arm"] == list(ARM_BUDGETS) and stated["removed_total"] == 282,
                  "declared_graph_budget", name)
            digest = sha(root / "graphs" / f"{name}.csv")
            check(stated["graph_sha256"] == digest, "graph_audit_hash", name)
            reconstructed_aliases[name] = first_hash.setdefault(digest, name)
            values = score_terms(original, candidate, source, gram)
            for key, value in values.items():
                close(row[key], value, "independent_" + key, rtol=3e-10, atol=1e-8)
                max_score_error[key] = max(max_score_error[key], abs(float(row[key]) - value))
    check(aliases == reconstructed_aliases, "canonical_graph_aliases")
    selected = js(root / "selection.json")
    check(len(selected) == 40, "selection_count")
    lookup = {(int(s["block"]), s["policy"]): s for s in selected}
    check(set(lookup) == {(b, p) for b in range(10) for p in POLICIES}, "complete_policy_grid")
    for (block, policy), s in lookup.items():
        candidate_index = int(s["candidate"])
        expected = (random.Random(990000 + block).randrange(64) if policy == "random" else
                    min(range(64), key=lambda k: (float(indexed[(block, k)]["J_" + policy]), k)))
        check(candidate_index == expected, "selector_fixed_tie_break_or_random", (block, policy))
        row = indexed[(block, candidate_index)]
        check(s["graph"] == row["graph"] and int(s["seed"]) == int(row["seed"]), "selection_candidate_identity")
        for key in ("J_mean", "J_coactivity", "J_shuffled", "J_shuffle_expectation"):
            check(float(s[key]) == float(row[key]), "selection_score_copy")
    unique = sorted({aliases[s["graph"]] for s in selected})
    planned = js(root / "planned-runs.json")
    expected_planned = [{"graph": g, "probe": p, "stem": g + "__" + p}
                        for g in ["original"] + unique for p in PROBES]
    check(planned == expected_planned, "deduplicated_run_plan")
    check(selection_lock["unique_selected_graphs"] == len(unique), "selection_unique_count")
    check(selection_lock["scientific_runs"] == len(planned) <= 164, "selection_run_count")
    return {"unique_selected_graphs": len(unique), "planned_runs": len(planned),
            "candidate_graphs_checked": 640, "scores_checked": 2560,
            "maximum_score_absolute_difference": dict(max_score_error)}


def truth(value):
    if isinstance(value, bool):
        return value
    check(value in ("True", "False", "true", "false"), "boolean_serialization", value)
    return str(value).lower() == "true"


def description(values):
    v = [float(x) for x in values if x is not None]
    return {"n": len(v), "mean": float(np.mean(v)) if v else None,
            "median": float(np.median(v)) if v else None,
            "minimum": min(v) if v else None, "maximum": max(v) if v else None}


def audit_runs_and_analysis(root, protocol, training):
    started = js(root / "run-start.json")
    start_time = datetime.fromisoformat(started["started_utc"].replace("Z", "+00:00"))
    selection_time = datetime.fromisoformat(js(root / "selection-lock.json")["locked_utc"].replace("Z", "+00:00"))
    check(start_time >= selection_time, "recorded_runs_after_selection_lock")
    for name in ("design-lock", "selection-lock"):
        check(started[name.replace("-", "_") + "_sha256"] == sha(root / (name + ".json")), "run_start_lock_hash")
    completion = js(root / "run-complete.json")
    records = completion["records"]
    planned = js(root / "planned-runs.json")
    check([{k: r[k] for k in ("graph", "probe", "stem")} for r in records] == planned, "run_plan_fully_executed")
    check(completion["scientific_runs"] == len(records), "completed_run_count")
    aliases = js(root / "graph-aliases.json")
    selected = js(root / "selection.json")
    arrays, count_metrics = {}, {}
    for record in records:
        graph_name, probe, stem = record["graph"], record["probe"], record["stem"]
        for ext in ("npz", "csv", "json"):
            check(record[ext + "_sha256"] == sha(root / "runs" / (stem + "." + ext)), "run_file_hash", stem)
        a = state(root / "runs" / (stem + ".npz"))
        arrays[(graph_name, probe)] = a
        count = rows(root / "runs" / (stem + ".csv"))
        check(len(count) == STEPS and [int(r["step"]) for r in count] == list(range(STEPS)), "count_csv_slots", stem)
        check([int(r["spikes"]) for r in count] == a[:, :, 0].sum(axis=1).tolist(), "count_csv_spikes", stem)
        e = graph(root / "graphs" / (graph_name + ".csv"))
        outdegree = np.bincount(e[:, 1], minlength=N)
        expected_visits = ((a[:, :, 0] > 0) @ outdegree).tolist()
        check([int(r["active_source_edge_visits"]) for r in count] == expected_visits, "active_edge_visits_from_spikes", stem)
        check([int(r["recurrent_messages"]) for r in count] == expected_visits, "explicit_messages_from_spikes", stem)
        check(all(0 <= int(r["active_chunks"]) <= N for r in count), "active_chunk_count_range", stem)
        count_metrics[(graph_name, probe)] = {"recurrent_messages": sum(expected_visits),
            "active_source_edge_visits": sum(expected_visits),
            "active_chunk_slot_sum": sum(int(r["active_chunks"]) for r in count), "edge_count": len(e)}
        meta = js(root / "runs" / (stem + ".json"))
        check((meta["steps"], meta["chunks"], meta["units_per_chunk"], meta["columns"]) == (300, 125, 100, 10), "run_metadata_dimensions")
        check(meta["mode"] == "explicit" and meta["timing_is_performance_benchmark"] is False, "run_mode_and_timing_scope")
        check(meta["within_chunk_equality_initial_and_all_slots"] is True and meta["within_chunk_checks"] == 37625, "run_within_chunk_assertions")
        check(meta["external_input_events"] == 1600 and meta["external_input_total_amplitude_f64"] == 240000, "run_input_dose")
        default_bits = int(np.array([-65], dtype=np.float32).view(np.uint32)[0])
        check(meta["initial_voltage_bits"] == [default_bits] * N, "run_initial_voltage")
        for first, voltage in zip(meta["first_step_slot"], meta["first_pre_update_voltage_bits"]):
            check((first is None and voltage is None) or (first is not None and 0 <= first < STEPS and voltage == default_bits), "first_execution_initial_voltage")
    check(np.array_equal(arrays[("original", "train")], training), "full_ten_field_archived_training_bridge")
    check(sha(root / "runs/original__train.csv") == sha(root / "inherited/training-original.csv"), "archived_training_counts_bridge")
    check(np.array_equal(state(root / "technical/repeat_original__train.npz"), training), "technical_repeat_state")
    check(sha(root / "technical/repeat_original__train.csv") == sha(root / "inherited/training-original.csv"), "technical_repeat_counts")
    results = {}
    for (name, probe), candidate in arrays.items():
        results[(name, probe)] = {**metrics(arrays[("original", probe)], candidate), **count_metrics[(name, probe)]}
    per_graph = rows(root / "analysis/per_graph.csv")
    check(len(per_graph) == len(results), "analysis_per_graph_count")
    check({(r["graph"], r["probe"]) for r in per_graph} == set(results), "analysis_per_graph_identities")
    max_vr_error = 0.0
    for row in per_graph:
        values = results[(row["graph"], row["probe"])]
        for key, value in values.items():
            if isinstance(value, bool):
                check(truth(row[key]) == value, "independent_" + key)
            else:
                close(row[key], value, "independent_" + key, rtol=3e-9, atol=3e-10)
        if values["van_rossum_tau1"] is not None:
            max_vr_error = max(max_vr_error, abs(float(row["van_rossum_tau1"]) - values["van_rossum_tau1"]))
    scales = js(root / "analysis/reference-scales.json")["scales"]
    for probe in PROBES:
        for key, field in (("V", 1), ("gE", 2), ("gI", 3)):
            v = arrays[("original", probe)][:, :, field].copy().view(np.float32).astype(np.float64)
            close(scales[probe][key], float(v.std(ddof=0)), "original_only_reference_scale")
    selected_map = {(int(s["block"]), s["policy"]): s for s in selected}
    per_policy = rows(root / "analysis/per_policy.csv")
    check(len(per_policy) == 160 and len({(r["block"], r["policy"], r["probe"]) for r in per_policy}) == 160, "analysis_policy_memberships")
    for row in per_policy:
        selection = selected_map[(int(row["block"]), row["policy"])]
        canonical = aliases[selection["graph"]]
        check(row["graph"] == selection["graph"], "policy_selection_identity")
        check(row["canonical_graph"] == canonical, "policy_canonical_identity")
        for key, value in results[(canonical, row["probe"])].items():
            if isinstance(value, bool):
                check(truth(row[key]) == value, "policy_metric_copy")
            else:
                close(row[key], value, "policy_metric_copy", rtol=3e-9)
    def loss(block, policy, probe):
        g = aliases[selected_map[(block, policy)]["graph"]]
        if probe != "heldout_mean":
            return results[(g, probe)]["raw_slot_l1"]
        values = [results[(g, p)]["raw_slot_l1"] for p in PROBES[1:]]
        return sum(values) / 3 if all(x is not None for x in values) else None
    contrasts = rows(root / "analysis/paired_contrasts.csv")
    expected_keys = {(b, p, c) for b in range(10) for p in (*PROBES, "heldout_mean") for c in ("random", "mean", "shuffled")}
    check(len(contrasts) == 150 and {(int(r["block"]), r["probe"], r["comparator"]) for r in contrasts} == expected_keys,
          "all_prespecified_paired_contrasts")
    difference_lookup = {}
    for row in contrasts:
        b, p, c = int(row["block"]), row["probe"], row["comparator"]
        a, other = loss(b, "coactivity", p), loss(b, c, p)
        value = a - other if a is not None and other is not None else None
        close(row["coactivity_loss"], a, "paired_coactivity_loss")
        close(row["comparator_loss"], other, "paired_comparator_loss")
        close(row["difference_coactivity_minus_comparator"], value, "paired_difference")
        expected_left = selected_map[(b, "coactivity")]["graph"]
        expected_right = selected_map[(b, c)]["graph"]
        check(row["coactivity_graph"] == expected_left and row["comparison_graph"] == expected_right, "paired_graph_identity")
        check(truth(row["same_selected_graph"]) == (aliases[expected_left] == aliases[expected_right]), "paired_graph_alias_equality")
        difference_lookup[(b, p, c)] = value
    contrast_summary = rows(root / "analysis/contrast_summary.csv")
    check(len(contrast_summary) == 15, "contrast_summary_count")
    for row in contrast_summary:
        values = [difference_lookup[(b, row["probe"], row["comparator"])] for b in range(10)]
        for key, value in description(values).items():
            close(row[key], value, "paired_summary_" + key)
        valid = [v for v in values if v is not None]
        for key, value in (("coactivity_better", sum(v < -1e-12 for v in valid)),
                           ("tied", sum(abs(v) <= 1e-12 for v in valid)),
                           ("coactivity_worse", sum(v > 1e-12 for v in valid))):
            close(row[key], value, "paired_summary_sign_counts")
    summary = js(root / "analysis/summary.json")
    primary_values = [difference_lookup[(b, "heldout_mean", "random")] for b in range(10)]
    check(summary["primary"]["probe"] == "heldout_mean" and summary["primary"]["comparator"] == "random", "locked_primary_endpoint")
    for key, value in description(primary_values).items():
        close(summary["primary"][key], value, "primary_summary_" + key)
    check(summary["performance_claim"] is False and summary["edge_counts_all_2845"] is True, "analysis_scope")
    endpoints = rows(root / "analysis/per_block_endpoints.csv")
    check(len(endpoints) == 40, "block_endpoint_count")
    for row in endpoints:
        b, policy = int(row["block"]), row["policy"]
        close(row["heldout_raw_slot_l1_mean"], loss(b, policy, "heldout_mean"), "equal_weight_heldout_endpoint")
        close(row["train_raw_slot_l1"], loss(b, policy, "train"), "training_endpoint")
    metric_summary = rows(root / "analysis/metric_summary.csv")
    metric_names = ("raw_slot_l1", "bin1ms_l1", "cumulative_l1", "Rcount", "van_rossum_tau1", "state_rms_standardized")
    check(len(metric_summary) == len(PROBES) * len(POLICIES) * len(metric_names), "metric_summary_count")
    for row in metric_summary:
        values = [results[(aliases[selected_map[(b, row["policy"])]["graph"]], row["probe"])][row["metric"]]
                  for b in range(10)]
        for key, value in description(values).items():
            close(row[key], value, "metric_summary_" + key, rtol=3e-9)
        close(row["undefined"], sum(v is None for v in values), "metric_summary_undefined")
    return {"run_arrays_checked": len(arrays), "all_ten_field_training_bridge": True,
            "complete_exponential_tail_distances_checked": len(results),
            "maximum_exponential_distance_absolute_difference": max_vr_error,
            "paired_contrasts_checked": 150, "primary": description(primary_values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--stage", choices=("design", "selection", "complete"), default="complete")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    args.output = args.output or root / "audit.json"
    report = {"audit": "independent activity-guided study audit", "stage": args.stage,
              "scope": "Recorded artifacts, scientific invariants, independent numerical recomputation; timestamps do not prove historical non-access.",
              "passed": False}
    try:
        protocol = js(root / "protocol.json")
        check((protocol["chunks"], protocol["units_per_chunk"], protocol["steps"], protocol["edges"]) == (125, 100, 300, 2845), "protocol_model_dimensions")
        check(protocol["dt_ms"] == 0.1 and protocol["budget"]["removed_by_arm"] == list(ARM_BUDGETS), "protocol_dt_budget")
        check(protocol["candidate_pool"]["blocks"] == 10 and protocol["candidate_pool"]["candidates_per_block"] == 64, "protocol_pool_size")
        check(protocol["selection"]["shuffle_repetitions"] == 32 and protocol["selection"]["policies"] == list(POLICIES), "protocol_selectors")
        check(protocol["heldout"] == list(PROBES[1:]), "protocol_heldouts")
        for rel, digest in js(root / "inherited-inputs-sha256.json").items():
            check(sha(root / rel) == digest, "inherited_input_hash", rel)
        design, design_time = locked(root, "design-lock.json")
        check(design.get("scientific_runs_started") is False, "design_before_scientific_runs")
        required_files = {"study.py", "reproduce.py", "analyze.py", "plot.py", "audit.py", "experiment.rs", "DRIVER.txt", "protocol.json", "inherited-inputs-sha256.json"}
        required_files.update(str(p.relative_to(root)) for d in ("source", "inherited", "events") for p in (root / d).rglob("*") if p.is_file())
        check(required_files.issubset(design["files"]), "design_lock_covers_science_and_data")
        report["inputs"] = validate_events(root)
        check(report["inputs"]["new_mask"] == sorted(random.Random(97001).sample(range(100), 20)), "heldout_mask_seed")
        original = graph(root / "inherited" / "original.csv")
        check(tuple(int((original[:, 0] == a).sum()) for a in range(4)) == (1467, 610, 648, 120), "original_arm_sizes")
        training = state(root / "inherited" / "training-original.npz")
        if args.stage != "design":
            report.update(audit_selection(root, protocol, original, training, design_time))
        if args.stage == "complete":
            report.update(audit_runs_and_analysis(root, protocol, training))
        report["passed"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["checks"] = dict(sorted(CHECKS.items()))
        report["successful_check_count"] = int(sum(CHECKS.values()))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "stage": args.stage, "checks": report["successful_check_count"], "report": str(args.output)}))


if __name__ == "__main__":
    main()
