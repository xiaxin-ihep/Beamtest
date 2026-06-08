#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = SCRIPT_DIR.parent
os.environ.setdefault("MPLCONFIGDIR", str(ANALYSIS_DIR / ".mplconfig"))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from siwecal_analysis.config import DEFAULT_OUTPUT_DIR


ASU_CURRENT_DATA = [
    ("2026_001", 0.34, 0.45),
    ("2026_002", 0.30, 2.2),
    ("2026_003", 0.31, 1.2),
    ("2026_004", 0.30, 1.8),
    ("2026_005", 0.38, 5.0),
    ("2026_006", 0.37, 10.0),
    ("2026_007", 0.40, 10.0),
    ("2026_008", 0.36, 4.8),
    ("2026_009", 0.40, 0.9),
]


def main() -> None:
    output_dir = DEFAULT_OUTPUT_DIR / "source_campaign" / "overview"
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = [row[0] for row in ASU_CURRENT_DATA]
    lv = np.array([row[1] for row in ASU_CURRENT_DATA], dtype=float)
    hv = np.array([row[2] for row in ASU_CURRENT_DATA], dtype=float)
    x = np.arange(len(labels))
    width = 0.38

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    axes[0].bar(x, lv, width=width, color="#497c88")
    axes[0].set_ylabel("LV current [A]", fontsize=18)
    axes[0].set_title("ASU leakage current summary", fontsize=22)
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].tick_params(axis="both", labelsize=13)
    axes[0].text(
        1.01,
        0.95,
        "LV: 3.6 or 3.7 V supply current",
        transform=axes[0].transAxes,
        ha="left",
        va="top",
        fontsize=11,
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "0.75", "boxstyle": "round,pad=0.3"},
    )

    axes[1].bar(x, hv, width=width, color="#c76d3a")
    axes[1].set_ylabel("HV130 current [uA]", fontsize=18)
    axes[1].set_xlabel("ASU ID", fontsize=18)
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].tick_params(axis="both", labelsize=13)
    axes[1].set_xticks(x, labels=labels, rotation=0)
    axes[1].text(
        1.01,
        0.95,
        "HV: leakage current at 130 V bias",
        transform=axes[1].transAxes,
        ha="left",
        va="top",
        fontsize=11,
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "0.75", "boxstyle": "round,pad=0.3"},
    )

    fig.tight_layout()
    fig.savefig(output_dir / "asu_leakage_currents.pdf")
    plt.close(fig)

    with (output_dir / "asu_leakage_currents.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["asu_id", "lv_current_a", "hv130_current_ua"])
        writer.writerows(ASU_CURRENT_DATA)


if __name__ == "__main__":
    main()
