#!/usr/bin/env python3
"""Render two report-only figures from completed, unchanged experiment tables.

This post-analysis renderer fits no model and selects no successful subset.
It is deliberately separate from the prospectively frozen scientific analysis.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np


GROUPS = ("A_degree", "B_aligned", "C_random")
LABELS = {"A_degree": "A: E/I statistics", "B_aligned": "B: Aligned groups",
          "C_random": "C: Random groups"}
COLORS = {"A_degree": "#C56C2F", "B_aligned": "#187F8C", "C_random": "#8B5A9F"}
MARKERS = {"A_degree": "o", "B_aligned": "s", "C_random": "^"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def readcsv(p):
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, help="New output directory; defaults to ROOT/report_figures")
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output.resolve() if args.output else root / "report_figures"
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"Refusing to overwrite nonempty output: {out}")
    filenames = ["legacy_diagnostics/phase-state-errors.csv", "analysis/prediction-data.csv",
                 "analysis/prediction-associations.csv", "analysis/source-subspace-coverage.csv",
                 "analysis/response-outcomes.csv", "predictors/training-summary.json"]
    before = {n: sha(root/n) for n in filenames}
    legacy = readcsv(root/filenames[0])
    predictions = readcsv(root/filenames[1])
    correlations = readcsv(root/filenames[2])
    coverage = readcsv(root/filenames[3])
    outcomes = readcsv(root/filenames[4])
    training = json.loads((root/filenames[5]).read_text())
    assert len(predictions) == 30
    assert training["rank5"] == 5 and training["secondary_training90_rank"] == 19
    out.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(out/".mpl-cache")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.titlesize": 12, "axes.labelsize": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.axisbelow": True, "savefig.dpi": 200,
                         "pdf.fonttype": 42, "ps.fonttype": 42,
                         "axes.edgecolor": "#53606A", "text.color": "#202A33",
                         "axes.labelcolor": "#202A33", "xtick.color": "#354450",
                         "ytick.color": "#354450"})
    group_handles = [Line2D([], [], linestyle="", marker=MARKERS[g], color=COLORS[g],
                            markersize=7, label=LABELS[g]) for g in GROUPS]
    numerical = {"legacy_phase_points": [], "response_points": [], "source_coverage": []}

    # Figure 1: every control and all three predeclared windows of the legacy
    # primary stimulus. No graph selection and no uncertainty bars inferred
    # from dependent conditional surrogates.
    fig, axes = plt.subplots(1, 3, figsize=(11.6, 5.3), sharey=True)
    fig.subplots_adjust(left=.08, right=.98, bottom=.29, top=.77, wspace=.15)
    phase_specs = [("conditioning", "Conditioning", "0–8 ms"),
                   ("early_recovery", "Early recovery", "8–15 ms"),
                   ("late_recovery", "Late recovery", "15–30 ms")]
    selected = [r for r in legacy if r["probe"] == "module_burst" and r["treatment"] in GROUPS]
    assert len(selected) == 45
    ymax = max(float(r["state_score"]) for r in selected)*1.12
    for pi, (ax, (phase, label, times)) in enumerate(zip(axes, phase_specs)):
        for gi, group in enumerate(GROUPS):
            points = sorted([r for r in selected if r["phase"] == phase and r["treatment"] == group],
                            key=lambda r: r["graph"])
            assert len(points) == 5
            y = np.array([float(r["state_score"]) for r in points])
            ax.scatter(gi+np.linspace(-.13, .13, 5), y, color=COLORS[group], marker=MARKERS[group],
                       s=44, alpha=.88, edgecolors="white", linewidths=.65, zorder=3)
            median = float(np.median(y))
            ax.plot([gi-.23, gi+.23], [median, median], color=COLORS[group], lw=3.1, zorder=4)
            numerical["legacy_phase_points"].extend({"graph": r["graph"], "group": group,
                                                      "phase": phase, "state_score": float(r["state_score"])}
                                                     for r in points)
        ax.set_title(f"{chr(65+pi)}   {label}\n{times}", loc="left", pad=12)
        ax.set_xticks(range(3), ["A", "B", "C"])
        ax.set_xlim(-.5, 2.5)
        ax.set_ylim(0, ymax)
        ax.grid(axis="y", color="#E4E8EC", lw=.7)
    axes[0].set_ylabel("State error (normalized model coordinates)\nLower is better")
    fig.suptitle("State preservation changes across trajectory windows", x=.08, y=.975,
                 ha="left", fontsize=16, fontweight="bold")
    fig.text(.08, .885, "Archived primary stimulus  ·  15 conditional rewires of one original network  ·  n = 5 per group",
             fontsize=10.5)
    fig.legend(handles=group_handles, loc="lower left", bbox_to_anchor=(.075, .14),
               frameon=False, ncol=3, handletextpad=.5, columnspacing=2.4)
    fig.text(.08, .095, "Points: all individual graphs; horizontal bars: group medians. The same graph set appears in every panel.",
             fontsize=9.6)
    fig.text(.08, .045, "V, gE and gI errors use the original trajectory’s full 30 ms channel scales; this is a finite-window model comparison.",
             fontsize=9.6)
    for ext in ("png", "pdf"):
        fig.savefig(out/f"legacy-phase-preservation.{ext}", facecolor="white", metadata={"Creator": "render_report_figures.py"} if ext == "pdf" else None)
    plt.close(fig)

    # Figure 2: both prespecified amplitudes, raw primary outcome and a fixed
    # zero-response comparator; coverage gives training/test context rather
    # than selecting a replacement predictor after seeing the test results.
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 5.8), gridspec_kw={"width_ratios": [1, 1, .95]})
    fig.subplots_adjust(left=.065, right=.985, bottom=.32, top=.76, wspace=.37)
    xall = np.array([float(r["activity_rank5"]) for r in predictions])
    ymax = max(float(r["response_fidelity"]) for r in predictions)*1.10
    for ai, (ax, condition) in enumerate(zip(axes[:2], ("small", "double"))):
        selected = [r for r in predictions if r["condition"] == condition]
        assert len(selected) == 15
        amplitudes = {float(r["amplitude"]) for r in selected}
        assert len(amplitudes) == 1
        amplitude = amplitudes.pop()
        for group in GROUPS:
            points = sorted([r for r in selected if r["treatment"] == group], key=lambda r: r["graph"])
            assert len(points) == 5
            ax.scatter([float(r["activity_rank5"]) for r in points],
                       [float(r["response_fidelity"]) for r in points],
                       s=55, color=COLORS[group], marker=MARKERS[group],
                       edgecolors="white", linewidths=.7, alpha=.95, zorder=3)
            numerical["response_points"].extend({"graph": r["graph"], "group": group,
                                                 "condition": condition,
                                                 "activity_rank5": float(r["activity_rank5"]),
                                                 "response_fidelity": float(r["response_fidelity"])}
                                                for r in points)
        association = [r for r in correlations if r["condition"] == condition and r["predictor"] == "activity_rank5"
                       and r["target"] == "response_fidelity" and r["subset"] == "all15"]
        assert len(association) == 1 and int(association[0]["n"]) == 15
        rho = float(association[0]["spearman"])
        original = [r for r in outcomes if r["graph"] == "original" and r["condition"] == condition]
        assert len(original) == 1
        zero_comparator = float(original[0]["original_response_rms"])
        ax.axhline(zero_comparator, color="#66737D", ls=(0, (4, 3)), lw=1.3, zorder=1)
        ax.set_title(f"{chr(65+ai)}   Pulse amplitude {amplitude:g}\nSpearman ρ = {rho:.3f}; n = 15", loc="left", pad=12)
        ax.set_xlabel("Relative rank-5 input-map distortion\n(frozen source subspace)")
        ax.set_xlim(float(xall.min())-.006, float(xall.max())+.006)
        ax.set_ylim(0, ymax)
        ax.set_xticks([.56, .58, .60, .62])
        ax.grid(color="#E4E8EC", lw=.7)
        numerical[f"zero_response_comparator_{condition}"] = zero_comparator
        numerical[f"spearman_{condition}"] = rho
    axes[0].set_ylabel("Perturbation-response error\n(normalized model coordinates)")
    axes[1].tick_params(labelleft=True)
    ax = axes[2]
    baseline = [r for r in coverage if r["condition"] == "baseline" and r["window"] == "primary_response"]
    assert len(baseline) == 1
    baseline = baseline[0]
    series = [np.array([training["rank5_energy_fraction"], float(baseline["rank5_energy_fraction"])]),
              np.array([training["secondary_training90_energy_fraction"], float(baseline["training90_energy_fraction"])])]
    coverage_colors = ["#366A94", "#AEBAC6"]
    for j, values in enumerate(series):
        positions = np.arange(2)+(j-.5)*.32
        ax.bar(positions, values, width=.29, color=coverage_colors[j], zorder=2)
        for x, val in zip(positions, values):
            ax.text(x, val+.028, f"{val:.1%}", ha="center", va="bottom", fontsize=10)
        numerical["source_coverage"].append({"rank": [5, 19][j], "training": float(values[0]),
                                               "new_baseline_primary_window": float(values[1])})
    ax.set_title("C   Source-activity coverage\nOriginal network; fixed bases", loc="left", pad=12)
    ax.set_xticks([0, 1], ["Training\n0–30 ms", "New baseline\n20–100 ms"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Spike-count energy captured")
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(axis="y", color="#E4E8EC", lw=.7)
    fig.suptitle("Testing a fixed activity-based predictor on a new stimulus", x=.065, y=.975,
                 ha="left", fontsize=16, fontweight="bold")
    fig.text(.065, .885, "All 15 conditional rewires  ·  5 per group  ·  Primary response window: 20–100 ms  ·  No test refitting",
             fontsize=10.5)
    legend_handles = group_handles+[Line2D([], [], color="#66737D", ls=(0, (4, 3)), lw=1.3,
                                         label="Zero-response comparator")]
    fig.legend(handles=legend_handles, loc="lower left", bbox_to_anchor=(.06, .13),
               frameon=False, ncol=2, handletextpad=.6, columnspacing=2.0, fontsize=10)
    fig.legend(handles=[Patch(facecolor=c, label=f"Rank {rank}") for c, rank in zip(coverage_colors, (5, 19))],
               loc="lower left", bbox_to_anchor=(.745, .145), frameon=False, ncol=2,
               handlelength=1.2, columnspacing=1.3, fontsize=10)
    fig.text(.065, .085, "Dashed line: error from predicting no perturbation response. A smaller own response is not necessarily better response fidelity.",
             fontsize=9.5)
    fig.text(.065, .04, "Amplitudes are model-input values. Correlations are descriptive across dependent rewires; the source subspaces are linear, not nonlinear manifolds.",
             fontsize=9.5)
    for ext in ("png", "pdf"):
        fig.savefig(out/f"fixed-predictor-response-evidence.{ext}", facecolor="white", metadata={"Creator": "render_report_figures.py"} if ext == "pdf" else None)
    plt.close(fig)
    assert before == {n: sha(root/n) for n in filenames}, "Scientific input changed during rendering"
    (out/"plot-data.json").write_text(json.dumps(numerical, indent=2, sort_keys=True, allow_nan=False)+"\n")
    provenance = {"status": "pass", "scope": "Post-analysis rendering only; no simulation, test refit or scientific-table modification.",
                  "input_sha256": before, "renderer_sha256": sha(Path(__file__).resolve()),
                  "graph_selection": "All 15 rewires, three legacy windows and both prespecified new amplitudes; no selection by success.",
                  "outputs_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out/"render-validation.json").write_text(json.dumps(provenance, indent=2, sort_keys=True)+"\n")
    print(f"Rendered two report figures (PNG and PDF), all input hashes unchanged: {out}")


if __name__ == "__main__":
    main()
