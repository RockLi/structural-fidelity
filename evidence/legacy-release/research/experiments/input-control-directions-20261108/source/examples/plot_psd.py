#!/usr/bin/env python3
"""
Plot Figure 4 for Paper 2: Population-Rate PSD comparison (Explicit vs LPU).

Reads the four CSV files exported by `measure_lpu_resources --release` and
produces a 2-panel figure saved as `fig4_psd_comparison.png`.

Usage
-----
    python3 examples/plot_psd.py

The script expects the CSV files in the current working directory (i.e. run
from the project root):
    psd_50k_sustained_explicit.csv
    psd_50k_sustained_lpu.csv
    psd_boundaryheavy_explicit.csv
    psd_boundaryheavy_lpu.csv
"""

import csv
import os
import sys
from pathlib import Path


def read_psd(filename: str) -> tuple[list[float], list[float]]:
    """Return (freq_hz, power) arrays from a two-column CSV."""
    freqs, powers = [], []
    path = Path(filename)
    if not path.exists():
        print(f"  [SKIP] {filename} not found — run the benchmark first.")
        return [], []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            freqs.append(float(row["frequency_hz"]))
            powers.append(float(row["power"]))
    return freqs, powers


def plot_psd() -> None:
    try:
        import matplotlib  # type: ignore
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        print("matplotlib not installed.  Install with: pip install matplotlib")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load all four spectra
    # ------------------------------------------------------------------
    fe_50k, pe_50k = read_psd("psd_50k_sustained_explicit.csv")
    fl_50k, pl_50k = read_psd("psd_50k_sustained_lpu.csv")
    fe_bh, pe_bh   = read_psd("psd_boundaryheavy_explicit.csv")
    fl_bh, pl_bh   = read_psd("psd_boundaryheavy_lpu.csv")

    if not (fe_50k and fl_50k and fe_bh and fl_bh):
        print("One or more PSD files are missing.  Cannot plot.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Layout: 1 row × 2 panels
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
    fig.suptitle(
        "Figure 4 — Population-Rate PSD: Explicit vs LPU 100%\n"
        "Balanced E/I microcircuit · Sustained drive · dt=1ms · DYN_STEPS=1000",
        fontsize=11,
    )

    max_freq = 500.0  # Hz — must include pathological LPU frequencies

    for ax, (fe, pe, fl, pl, title) in zip(
        axes,
        [
            (fe_50k, pe_50k, fl_50k, pl_50k, "50k units / 500 chunks  (Sustained)"),
            (fe_bh,  pe_bh,  fl_bh,  pl_bh,  "Boundary-Heavy  (1k units, p_ei=0.8, p_ie=1.0)"),
        ],
    ):
        # Clip to max_freq
        def clip(f, p):
            pairs = [(x, y) for x, y in zip(f, p) if x <= max_freq]
            if not pairs:
                return f, p
            fc, pc = zip(*pairs)
            return list(fc), list(pc)

        fe_c, pe_c = clip(fe, pe)
        fl_c, pl_c = clip(fl, pl)

        ax.semilogy(fe_c, pe_c, color="#2563EB", linewidth=1.5, label="Explicit")
        ax.semilogy(fl_c, pl_c, color="#DC2626", linewidth=1.5, linestyle="--", label="LPU 100%")
        ax.set_title(title, fontsize=9, pad=6)
        ax.set_xlabel("Frequency (Hz)", fontsize=9)
        ax.set_ylabel("Power (a.u., log scale)", fontsize=9)
        ax.set_xlim(0, max_freq)
        ax.legend(fontsize=9)
        ax.grid(True, which="both", alpha=0.25)
        ax.tick_params(labelsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.88])

    out = "fig4_psd_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")


if __name__ == "__main__":
    plot_psd()
