#!/usr/bin/env python3
"""Independent audit of the nested-budget, training-gated follow-up.

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
FULL_BUDGETS = (146, 60, 64, 12)
BUDGETS = {"p01": (14, 6, 6, 2), "p02": (30, 12, 12, 2)}
CHECKS: Counter = Counter()
READ_FILES = set()
AUDIT_ROOT = None


def remember(path):
    path = Path(path).resolve()
    if AUDIT_ROOT is not None:
        check(path.is_relative_to(AUDIT_ROOT), "read_path_within_study", str(path))
        READ_FILES.add(str(path.relative_to(AUDIT_ROOT)))


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
    remember(path)
    return json.loads(Path(path).read_text())


def rows(path):
    remember(path)
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def sha(path):
    remember(path)
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


def graph_invariants(original, candidate, label, budgets):
    check(np.array_equal(original[:, (0, 1, 3, 4)], candidate[:, (0, 1, 3, 4)]),
          "row_source_arm_weight_delay_preserved", label)
    # Exact per-node, per-arm multisets jointly preserve degrees, weights,
    # delays, and strengths without relying on floating-point sums.
    for col, name in ((1, "out"), (2, "in")):
        key_cols = (0, col, 3, 4)
        check(Counter(map(tuple, original[:, key_cols])) == Counter(map(tuple, candidate[:, key_cols])),
              "per_node_arm_" + name + "_weight_delay_multiset", label)
    orig_pairs = set(map(tuple, original[:, 1:3]))
    for arm, budget in enumerate(budgets):
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
    length = source.shape[1]
    temporal_sum = input_difference.sum(axis=2)
    mean_difference = temporal_sum / length
    mean = float(np.square(temporal_sum).sum()) / length
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
    remember(path)
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


def independent_prefixes(original, seed):
    """Replay full old RNG schedule, then take nested accepted-pair prefixes."""
    rng = random.Random(seed)
    full = original.copy()
    prefix = {key: original.copy() for key in BUDGETS}
    initial = {tuple(x) for x in original[:, 1:3]}
    occupied = set(initial)
    histories = []
    for arm, budget in enumerate(FULL_BUDGETS):
        remaining = [i for i, row in enumerate(original) if row[0] == arm]
        moved, history = 0, []
        for proposals in range(1, 200001):
            i, j = rng.sample(remaining, 2)
            u, v = map(int, full[i, 1:3])
            x, y = map(int, full[j, 1:3])
            proposed = ((u, y), (x, v))
            if u == x or v == y or u == y or x == v:
                continue
            if any(pair in initial or pair in occupied for pair in proposed):
                continue
            if tuple(full[i, 3:5]) != tuple(full[j, 3:5]):
                continue
            occupied.difference_update(((u, v), (x, y)))
            occupied.update(proposed)
            full[i, 2], full[j, 2] = y, v
            remaining = [k for k in remaining if k not in (i, j)]
            moved += 2
            history.append({"rows": [i, j], "original_targets": [v, y],
                            "new_targets": [y, v], "proposal": proposals})
            for key, counts in BUDGETS.items():
                if moved <= counts[arm]:
                    prefix[key][i, 2], prefix[key][j, 2] = y, v
            if moved == budget:
                break
        check(moved == budget, "candidate_full_fixed_cap_success", (seed, arm))
        histories.append({"arm": arm, "proposals": proposals, "swaps": history})
    return full, prefix, histories


def graph_bytes(array):
    header = "arm,source,target,weight_bits,delay\n"
    return (header + "".join(",".join(str(int(x)) for x in row) + "\n" for row in array)).encode()


def audit_selection(root, protocol, original, training, design_time):
    selection_lock, selection_time = locked(root, "selection-lock.json")
    check(selection_time >= design_time, "selection_after_design")
    check(selection_lock.get("scientific_runs_started") is False, "selection_before_runs")
    check(np.array_equal(graph(root / "graphs/original.csv"), original), "unchanged_original_graph")
    candidates = rows(root / "candidates.csv")
    check(len(candidates) == 1280, "candidate_count")
    indexed = {(r["budget"], int(r["block"]), int(r["candidate"])): r for r in candidates}
    check(set(indexed) == {(q, b, k) for q in BUDGETS for b in range(10) for k in range(64)},
          "complete_unique_candidate_grid")
    aliases = js(root / "graph-aliases.json")
    assertions = {r["graph"]: r for r in js(root / "graph-audit.json")}
    sequences = {(int(r["block"]), int(r["candidate"])): r for r in js(root / "prefix-sequences.json")}
    prior_hash = js(root / "inherited/prior-full-graph-sha256.json")
    check(len(assertions) == 1280 and len(sequences) == len(prior_hash) == 640, "graph_audit_record_counts")
    source = training[:EMISSIONS, :, 0].T.astype(np.float64) / UNITS
    hashes, max_score_error = {}, Counter()
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
            old_name = f"b{block:02d}_c{index:02d}"
            seed = 980000 + 1000 * block + index
            full, prefixes, history = independent_prefixes(original, seed)
            digest = hashlib.sha256(graph_bytes(full)).hexdigest()
            check(digest == prior_hash[old_name], "complete_old_graph_hash_reconstructed", old_name)
            seq = sequences[(block, index)]
            check(seq["seed"] == seed and seq["prior_graph"] == old_name and seq["full_sha256"] == digest,
                  "prefix_prior_identity", old_name)
            check(seq["sequence"] == history, "entire_old_proposal_schedule", old_name)
            changed = [set(np.flatnonzero(prefixes[q][:, 2] != original[:, 2])) for q in BUDGETS]
            check(changed[0] < changed[1], "nested_prefix_changed_rows", old_name)
            for key, budget in BUDGETS.items():
                row = indexed[(key, block, index)]
                name = key + "_" + old_name
                check(row["graph"] == name and int(row["seed"]) == seed, "candidate_name_seed", name)
                candidate = graph(root / "graphs" / f"{name}.csv")
                graph_invariants(original, candidate, name, budget)
                check(np.array_equal(candidate, prefixes[key]), "exact_small_budget_prefix", name)
                stated = assertions[name]
                check(stated["removed_by_arm"] == list(budget) and stated["removed_total"] == sum(budget),
                      "declared_graph_budget", name)
                file_hash = sha(root / "graphs" / f"{name}.csv")
                check(stated["graph_sha256"] == file_hash, "graph_audit_hash", name)
                hashes[name] = file_hash
                values = score_terms(original, candidate, source, gram)
                for field, value in values.items():
                    close(row[field], value, "independent_" + field, rtol=3e-10, atol=1e-8)
                    if field in ("J_mean", "J_coactivity"):
                        check((float(row[field]) == 0) == (value == 0), "exact_zero_" + field, name)
                    max_score_error[field] = max(max_score_error[field], abs(float(row[field]) - value))
    first_hash, reconstructed_aliases = {}, {}
    for row in sorted(candidates, key=lambda r: (r["budget"], int(r["block"]), int(r["candidate"]))):
        name = row["graph"]
        reconstructed_aliases[name] = first_hash.setdefault(hashes[name], name)
    check(aliases == reconstructed_aliases, "canonical_graph_aliases")
    selected = js(root / "selection.json")
    check(len(selected) == 80, "selection_count")
    lookup = {(s["budget"], int(s["block"]), s["policy"]): s for s in selected}
    check(set(lookup) == {(q, b, p) for q in BUDGETS for b in range(10) for p in POLICIES}, "complete_policy_grid")
    for (key, block, policy), selected_row in lookup.items():
        candidate_index = int(selected_row["candidate"])
        expected = (random.Random(990000 + block).randrange(64) if policy == "random" else
                    min(range(64), key=lambda k: (float(indexed[(key, block, k)]["J_" + policy]), k)))
        check(candidate_index == expected, "selector_fixed_tie_break_or_random", (key, block, policy))
        row = indexed[(key, block, candidate_index)]
        check(selected_row["graph"] == row["graph"] and int(selected_row["seed"]) == int(row["seed"]), "selection_candidate_identity")
        for field in ("J_mean", "J_coactivity", "J_shuffled", "J_shuffle_expectation"):
            check(float(selected_row[field]) == float(row[field]), "selection_score_copy")
    unique = sorted({aliases[s["graph"]] for s in selected})
    for stage, probes in (("train", ("train",)), ("migration", PROBES[1:])):
        planned = js(root / f"planned-{stage}.json")
        expected_planned = [{"graph": g, "probe": p, "stem": g + "__" + p}
                            for g in ["original"] + unique for p in probes]
        check(planned == expected_planned, "deduplicated_" + stage + "_plan")
    check(selection_lock["unique_selected_graphs"] == len(unique), "selection_unique_count")
    check(selection_lock["maximum_training_runs"] == len(unique) + 1 <= 81, "selection_training_run_count")
    return {"unique_selected_graphs": len(unique), "training_runs_planned": len(unique) + 1,
            "candidate_graphs_checked": 1280, "old_full_graph_hashes_reconstructed": 640,
            "scores_checked": 5120, "maximum_score_absolute_difference": dict(max_score_error)}


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


def audit_runs_and_analysis(root, stage, training):
    probes = ("train",) if stage == "train" else PROBES[1:]
    endpoint = "train" if stage == "train" else "migration_mean"
    out = root / ("analysis-" + stage)
    started = js(root / f"run-{stage}-start.json")
    start_time = datetime.fromisoformat(started["started_utc"].replace("Z", "+00:00"))
    selection_time = datetime.fromisoformat(js(root / "selection-lock.json")["locked_utc"].replace("Z", "+00:00"))
    check(start_time >= selection_time, "recorded_runs_after_selection_lock")
    for name in ("design-lock", "selection-lock"):
        check(started[name.replace("-", "_") + "_sha256"] == sha(root / (name + ".json")), "run_start_lock_hash")
    completion = js(root / f"run-{stage}-complete.json")
    records = completion["records"]
    planned = js(root / f"planned-{stage}.json")
    check([{k: r[k] for k in ("graph", "probe", "stem")} for r in records] == planned, "run_plan_fully_executed")
    check(completion["scientific_runs"] == len(records) and completion["stage"] == stage, "completed_run_count_stage")
    if stage == "train":
        expected_stems = {r["stem"] for r in planned}
        check({p.stem for p in (root / "runs").glob("*.npz")} == expected_stems, "training_only_runs_before_gate")
        check(not (root / "run-migration-start.json").exists(), "migration_not_started_before_training_audit")
    else:
        training_audit = js(root / "audit-train.json")
        check(training_audit["status"] == "pass" and training_audit["gate_verified"] is True, "prior_training_audit_passed")
        check(training_audit["gate_sha256"] == sha(root / "gate.json"), "migration_gate_matches_audit")
        check(js(root / "gate.json")["proceed_migration"] is True, "migration_allowed_by_joint_gate")
        for rel, digest in training_audit["files"].items():
            check(sha(root / rel) == digest, "training_evidence_unchanged_before_migration", rel)
    aliases = js(root / "graph-aliases.json")
    selected = js(root / "selection.json")
    arrays, counters = {}, {}
    for record in records:
        graph_name, probe, stem = record["graph"], record["probe"], record["stem"]
        check(probe in probes, "stage_probe_scope", stem)
        for ext in ("npz", "csv", "json"):
            check(record[ext + "_sha256"] == sha(root / "runs" / (stem + "." + ext)), "run_file_hash", stem)
        array = state(root / "runs" / (stem + ".npz"))
        arrays[(graph_name, probe)] = array
        count = rows(root / "runs" / (stem + ".csv"))
        check(len(count) == STEPS and [int(r["step"]) for r in count] == list(range(STEPS)), "count_csv_slots", stem)
        check([int(r["spikes"]) for r in count] == array[:, :, 0].sum(axis=1).tolist(), "count_csv_spikes", stem)
        edges = graph(root / "graphs" / (graph_name + ".csv"))
        outdegree = np.bincount(edges[:, 1], minlength=N)
        visits = ((array[:, :, 0] > 0) @ outdegree).tolist()
        check([int(r["active_source_edge_visits"]) for r in count] == visits, "active_edge_visits_from_spikes", stem)
        check([int(r["recurrent_messages"]) for r in count] == visits, "explicit_messages_from_spikes", stem)
        check(all(0 <= int(r["active_chunks"]) <= N for r in count), "active_chunk_count_range", stem)
        counters[(graph_name, probe)] = {"recurrent_messages": sum(visits), "active_source_edge_visits": sum(visits),
            "active_chunk_slot_sum": sum(int(r["active_chunks"]) for r in count), "edge_count": len(edges)}
        meta = js(root / "runs" / (stem + ".json"))
        check((meta["steps"], meta["chunks"], meta["units_per_chunk"], meta["columns"]) == (300, 125, 100, 10), "run_metadata_dimensions")
        check(meta["mode"] == "explicit" and meta["timing_is_performance_benchmark"] is False, "run_mode_and_timing_scope")
        check(meta["within_chunk_equality_initial_and_all_slots"] is True and meta["within_chunk_checks"] == 37625, "run_within_chunk_assertions")
        check(meta["external_input_events"] == 1600 and meta["external_input_total_amplitude_f64"] == 240000, "run_input_dose")
        default_bits = int(np.array([-65], dtype=np.float32).view(np.uint32)[0])
        check(meta["initial_voltage_bits"] == [default_bits] * N, "run_initial_voltage")
        for first, voltage in zip(meta["first_step_slot"], meta["first_pre_update_voltage_bits"]):
            check((first is None and voltage is None) or (first is not None and 0 <= first < STEPS and voltage == default_bits), "first_execution_initial_voltage")
    if stage == "train":
        check(np.array_equal(arrays[("original", "train")], training), "full_ten_field_archived_training_bridge")
        check(sha(root / "runs/original__train.csv") == sha(root / "inherited/training-original.csv"), "archived_training_counts_bridge")
        check(np.array_equal(state(root / "technical/repeat_original__train.npz"), training), "technical_repeat_state")
        check(sha(root / "technical/repeat_original__train.csv") == sha(root / "inherited/training-original.csv"), "technical_repeat_counts")
    results = {(name, probe): {**metrics(arrays[("original", probe)], array), **counters[(name, probe)]}
               for (name, probe), array in arrays.items()}
    per_graph = rows(out / "per_graph.csv")
    check(len(per_graph) == len(results) and {(r["graph"], r["probe"]) for r in per_graph} == set(results), "analysis_per_graph_identities")
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
    scales = js(out / "reference-scales.json")["scales"]
    for probe in probes:
        for key, field in (("V", 1), ("gE", 2), ("gI", 3)):
            values = arrays[("original", probe)][:, :, field].copy().view(np.float32).astype(np.float64)
            close(scales[probe][key], float(values.std(ddof=0)), "original_only_reference_scale")
    selected_map = {(r["budget"], int(r["block"]), r["policy"]): r for r in selected}
    per_policy = rows(out / "per_policy.csv")
    expected_policy_keys = {(q, b, p, probe) for q in BUDGETS for b in range(10) for p in POLICIES for probe in probes}
    check(len(per_policy) == len(expected_policy_keys) and
          {(r["budget"], int(r["block"]), r["policy"], r["probe"]) for r in per_policy} == expected_policy_keys,
          "analysis_policy_memberships")
    for row in per_policy:
        selection = selected_map[(row["budget"], int(row["block"]), row["policy"])]
        canonical = aliases[selection["graph"]]
        check(row["graph"] == selection["graph"] and row["canonical_graph"] == canonical, "policy_selection_identity")
        for key, value in results[(canonical, row["probe"])].items():
            if isinstance(value, bool):
                check(truth(row[key]) == value, "policy_metric_copy")
            else:
                close(row[key], value, "policy_metric_copy", rtol=3e-9)
    def policy_metrics(budget, block, policy, probe):
        return results[(aliases[selected_map[(budget, block, policy)]["graph"]], probe)]
    def loss(budget, block, policy, probe):
        if probe != "migration_mean":
            return policy_metrics(budget, block, policy, probe)["raw_slot_l1"]
        values = [policy_metrics(budget, block, policy, p)["raw_slot_l1"] for p in PROBES[1:]]
        return sum(values) / 3 if all(v is not None for v in values) else None
    
    contrast_probes = probes if stage == "train" else (*probes, "migration_mean")
    contrasts = rows(out / "paired_contrasts.csv")
    expected = {(q, b, p, c) for q in BUDGETS for b in range(10) for p in contrast_probes for c in ("random", "mean", "shuffled")}
    check(len(contrasts) == len(expected) and {(r["budget"], int(r["block"]), r["probe"], r["comparator"]) for r in contrasts} == expected,
          "all_prespecified_paired_contrasts")
    differences = {}
    for row in contrasts:
        q, b, p, c = row["budget"], int(row["block"]), row["probe"], row["comparator"]
        left, right = loss(q, b, "coactivity", p), loss(q, b, c, p)
        difference = left - right if left is not None and right is not None else None
        close(row["coactivity_loss"], left, "paired_coactivity_loss")
        close(row["comparator_loss"], right, "paired_comparator_loss")
        close(row["difference_coactivity_minus_comparator"], difference, "paired_difference")
        lgraph, rgraph = selected_map[(q, b, "coactivity")]["graph"], selected_map[(q, b, c)]["graph"]
        check(row["coactivity_graph"] == lgraph and row["comparison_graph"] == rgraph, "paired_graph_identity")
        check(truth(row["same_selected_graph"]) == (aliases[lgraph] == aliases[rgraph]), "paired_graph_alias_equality")
        differences[(q, b, p, c)] = difference
    expected_summaries = {}
    for q in BUDGETS:
        for probe in contrast_probes:
            for comparator in ("random", "mean", "shuffled"):
                values = [differences[(q, b, probe, comparator)] for b in range(10)]
                valid = [v for v in values if v is not None]
                expected_summaries[(q, probe, comparator)] = {
                    "budget": q, "probe": probe, "comparator": comparator, **description(values),
                    "coactivity_better": sum(v < -1e-12 for v in valid), "tied": sum(abs(v) <= 1e-12 for v in valid),
                    "coactivity_worse": sum(v > 1e-12 for v in valid),
                    "same_selected_graph": sum(aliases[selected_map[(q, b, "coactivity")]["graph"]] ==
                                               aliases[selected_map[(q, b, comparator)]["graph"]] for b in range(10))}
    def verify_summary(row, expected_row, prefix):
        check((row["budget"], row["probe"], row["comparator"]) ==
              (expected_row["budget"], expected_row["probe"], expected_row["comparator"]), prefix + "_identity")
        for field, value in expected_row.items():
            if field not in ("budget", "probe", "comparator"):
                close(row[field], value, prefix + "_" + field)
    contrast_summary = rows(out / "contrast_summary.csv")
    check(len(contrast_summary) == len(expected_summaries), "contrast_summary_count")
    for row in contrast_summary:
        verify_summary(row, expected_summaries[(row["budget"], row["probe"], row["comparator"])], "paired_summary")
    summary = js(out / "summary.json")
    check(summary["stage"] == stage and summary["performance_claim"] is False and summary["edge_counts_all_2845"] is True,
          "analysis_stage_scope")
    for row in summary["contrasts"]:
        verify_summary(row, expected_summaries[(row["budget"], row["probe"], row["comparator"])], "json_paired_summary")
    endpoints = rows(out / "per_block_endpoints.csv")
    check(len(endpoints) == 80, "block_endpoint_count")
    for row in endpoints:
        close(row["endpoint_raw_slot_l1"], loss(row["budget"], int(row["block"]), row["policy"], endpoint), "block_endpoint")
        check(row["endpoint_probe"] == endpoint, "endpoint_probe")
    metric_summary = rows(out / "metric_summary.csv")
    metric_names = ("raw_slot_l1", "bin1ms_l1", "cumulative_l1", "Rcount", "van_rossum_tau1", "state_rms_standardized")
    check(len(metric_summary) == len(BUDGETS) * len(probes) * len(POLICIES) * len(metric_names), "metric_summary_count")
    for row in metric_summary:
        values = [policy_metrics(row["budget"], b, row["policy"], row["probe"])[row["metric"]] for b in range(10)]
        for key, value in description(values).items():
            close(row[key], value, "metric_summary_" + key, rtol=3e-9)
        close(row["undefined"], sum(v is None for v in values), "metric_summary_undefined")
    zeros = rows(out / "zero_summary.csv")
    check(len(zeros) == len(BUDGETS) * len(probes) * len(POLICIES), "zero_summary_count")
    for row in zeros:
        values = [policy_metrics(row["budget"], b, row["policy"], row["probe"]) for b in range(10)]
        close(row["n"], 10, "zero_summary_denominator")
        for field, source_key in (("zero_raw_slot", "Dslot"), ("zero_bin1ms", "D1ms"),
                                  ("zero_cumulative", "Dcount"), ("zero_reference_spikes", "reference_spikes")):
            close(row[field], sum(v[source_key] == 0 for v in values), "independent_" + field)
        close(row["recorded_bits_equal"], sum(v["recorded_bits_equal"] for v in values), "independent_zero_full_record")
    score_pairs = rows(out / "training_score_pairs.csv")
    check(len(score_pairs) == 60, "score_pair_count")
    for row in score_pairs:
        key, block, comparator = row["budget"], int(row["block"]), row["comparator"]
        left = selected_map[(key, block, "coactivity")]["J_coactivity"]
        right = selected_map[(key, block, comparator)]["J_coactivity"]
        close(row["coactivity_J"], left, "score_pair_coactivity")
        close(row["comparator_J"], right, "score_pair_comparator")
        close(row["ratio_coactivity_to_comparator"], left / right if right else None, "score_pair_ratio")
        close(row["relative_reduction"], 1 - left / right if right else None, "score_pair_reduction")
    report = {"run_arrays_checked": len(arrays), "complete_exponential_tail_distances_checked": len(results),
              "maximum_exponential_distance_absolute_difference": max_vr_error,
              "paired_contrasts_checked": len(contrasts), "zero_summary_rows_checked": len(zeros)}
    if stage == "train":
        gate = js(root / "gate.json")
        check(gate == js(out / "gate.json") == summary["gate"], "gate_copies_identical")
        check(gate["epsilon"] == 1e-12 and gate["stage"] == "train", "gate_fixed_scope")
        check(gate["training_per_policy_sha256"] == sha(out / "per_policy.csv"), "gate_binds_policy_metrics")
        decisions = {d["budget"]: d for d in gate["budgets"]}
        check(set(decisions) == set(BUDGETS), "gate_requires_both_budgets")
        independent_passes = {}
        for key in BUDGETS:
            observed = {c: expected_summaries[(key, "train", c)] for c in ("random", "mean", "shuffled")}
            for c, observed_row in observed.items():
                verify_summary(decisions[key]["observed"][c], observed_row, "gate_observed")
            random_result = observed["random"]
            conditions = {"complete_pairs": all(r["n"] == 10 for r in observed.values()),
                "random_mean_negative": random_result["mean"] is not None and random_result["mean"] < -1e-12,
                "random_median_negative": random_result["median"] is not None and random_result["median"] < -1e-12,
                "random_at_least_seven_strict_wins": random_result["coactivity_better"] >= 7}
            for c in ("mean", "shuffled"):
                conditions[c + "_mean_noninferior"] = observed[c]["mean"] is not None and observed[c]["mean"] <= 1e-12
                conditions[c + "_wins_at_least_losses"] = observed[c]["coactivity_better"] >= observed[c]["coactivity_worse"]
            check(decisions[key]["conditions"] == conditions, "all_independent_gate_conditions", key)
            independent_passes[key] = all(conditions.values())
            check(decisions[key]["passed"] == independent_passes[key], "independent_budget_gate", key)
        proceed = all(independent_passes.values())
        check(gate["proceed_migration"] is proceed, "independent_joint_gate")
        ledger = js(root / "migration-ledger.json")
        check(ledger["status"] == ("authorized_pending" if proceed else "not_run") and ledger["scientific_runs"] == 0,
              "migration_ledger_before_any_migration")
        check(ledger["gate_sha256"] == sha(root / "gate.json"), "migration_ledger_gate_hash")
        report.update(gate_verified=True, gate_sha256=sha(root / "gate.json"),
                      proceed_migration=proceed, budget_gate_passes=independent_passes)
    # Bind every stage analysis table and JSON, including definitions/provenance.
    for path in sorted(out.glob("*.json")) + sorted(out.glob("*.csv")):
        sha(path)
    return report


def main():
    global AUDIT_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--stage", choices=("design", "selection", "train", "migration"), default="train")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    AUDIT_ROOT = root
    args.output = args.output or root / ("audit-" + args.stage + ".json")
    report = {"audit": "independent nested-budget study audit", "stage": args.stage,
              "scope": "Recorded artifacts, structural invariants, independent numerical recomputation and continuation decision; timestamps alone do not prove historical non-access.",
              "status": "fail", "passed": False}
    try:
        protocol = js(root / "protocol.json")
        check((protocol["chunks"], protocol["units_per_chunk"], protocol["steps"], protocol["edges"]) == (125, 100, 300, 2845), "protocol_model_dimensions")
        check(protocol["dt_ms"] == 0.1 and protocol["training_probe"] == "train", "protocol_dt_training")
        check(protocol["candidate_pool"]["blocks"] == 10 and protocol["candidate_pool"]["candidates_per_block"] == 64, "protocol_pool_size")
        check(protocol["selection"]["shuffle_repetitions"] == 32 and protocol["selection"]["policies"] == list(POLICIES), "protocol_selectors")
        check(protocol["migration_probes"] == list(PROBES[1:]), "protocol_known_migration_inputs")
        for key, values in BUDGETS.items():
            check(protocol["budgets"][key]["removed_by_arm"] == list(values), "protocol_arm_budget", key)
            check(protocol["budgets"][key]["removed_total"] == sum(values), "protocol_total_budget", key)
            close(protocol["budgets"][key]["fraction"], sum(values) / 2845, "protocol_actual_budget_fraction", rtol=1e-14)
        gate_rule = protocol["continuation_gate"]
        check(gate_rule["epsilon"] == 1e-12 and gate_rule["both_budgets_required"] is True and gate_rule["required_complete_pairs"] == 10, "protocol_gate_scope")
        check(gate_rule["random"] == {"mean_less_than": -1e-12, "median_less_than": -1e-12, "minimum_strict_wins": 7}, "protocol_random_gate")
        check(gate_rule["specificity"] == {"comparators": ["mean", "shuffled"], "mean_at_most": 1e-12, "wins_at_least_losses": True}, "protocol_control_guard")
        for rel, digest in js(root / "inherited-inputs-sha256.json").items():
            check(sha(root / rel) == digest, "inherited_input_hash", rel)
        design, design_time = locked(root, "design-lock.json")
        check(design.get("scientific_runs_started") is False, "design_before_scientific_runs")
        required_files = {"study.py", "reproduce.py", "analyze.py", "plot.py", "audit.py", "README.txt", "experiment.rs", "DRIVER.txt", "protocol.json", "inherited-inputs-sha256.json"}
        required_files.update(str(p.relative_to(root)) for d in ("source", "inherited", "events") for p in (root / d).rglob("*") if p.is_file())
        check(required_files.issubset(design["files"]), "design_lock_covers_science_and_data")
        report["inputs"] = validate_events(root)
        prior = js(root / "inherited/prior-protocol.json")
        for probe in PROBES:
            check(sha(root / "events" / (probe + ".csv")) == prior["inputs"][probe]["event_sha256"], "exact_prior_known_input", probe)
        original = graph(root / "inherited/original.csv")
        check(tuple(int((original[:, 0] == a).sum()) for a in range(4)) == (1467, 610, 648, 120), "original_arm_sizes")
        training = state(root / "inherited/training-original.npz")
        if args.stage in ("selection", "train"):
            report.update(audit_selection(root, protocol, original, training, design_time))
        elif args.stage == "migration":
            locked(root, "selection-lock.json")
        if args.stage in ("train", "migration"):
            report.update(audit_runs_and_analysis(root, args.stage, training))
        report["passed"] = True
        report["status"] = "pass"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        # The migration ledger is a mutable administrative status. The immutable
        # gate and all source/selection/training artifacts remain hash-bound.
        READ_FILES.discard("migration-ledger.json")
        report["missing_read_files"] = [rel for rel in sorted(READ_FILES) if not (root / rel).is_file()]
        report["files"] = {rel: sha(root / rel) for rel in sorted(READ_FILES) if (root / rel).is_file()}
        report["checks"] = dict(sorted(CHECKS.items()))
        report["successful_check_count"] = int(sum(CHECKS.values()))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "pass", "stage": args.stage, "checks": report["successful_check_count"],
                      "proceed_migration": report.get("proceed_migration"), "report": str(args.output)}))


if __name__ == "__main__":
    main()
