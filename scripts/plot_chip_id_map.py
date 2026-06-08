#!/usr/bin/env python3
from __future__ import annotations

import argparse
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

from siwecal_analysis.config import DEFAULT_ECAL_MAPPING, DEFAULT_OUTPUT_DIR
from siwecal_analysis.mapping import load_ecal_mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot the chip-ID layout corresponding to the 32x32 hit map.")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR / "source_campaign" / "overview" / "chip_id_position_map.pdf")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mapping = load_ecal_mapping(args.mapping_file)

    chip_map = np.zeros((32, 32), dtype=int)
    for x in range(32):
        for y in range(32):
            chip_map[31 - y, 31 - x] = int(mapping[x, y, 0])

    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 8))
    image = ax.imshow(chip_map, origin="lower", cmap="tab20", interpolation="nearest", vmin=0, vmax=15)
    ax.set_title("Chip ID layout on the 32x32 hit map", fontsize=22)
    ax.set_xlabel("x index", fontsize=20)
    ax.set_ylabel("y index", fontsize=20)
    ax.tick_params(axis="both", labelsize=14)

    for chip in range(16):
        ys, xs = np.where(chip_map == chip)
        if xs.size == 0:
            continue
        x_center = float(np.mean(xs))
        y_center = float(np.mean(ys))
        ax.text(
            x_center,
            y_center,
            str(chip),
            ha="center",
            va="center",
            fontsize=18,
            fontweight="bold",
            color="white",
            bbox={"facecolor": "black", "alpha": 0.35, "pad": 2, "edgecolor": "none"},
        )

    for edge in [7.5, 15.5, 23.5]:
        ax.axvline(edge, color="white", linewidth=1.0, alpha=0.8)
        ax.axhline(edge, color="white", linewidth=1.0, alpha=0.8)

    cbar = fig.colorbar(image, ax=ax, ticks=np.arange(16), shrink=0.85)
    cbar.set_label("Chip ID", fontsize=16)
    cbar.ax.tick_params(labelsize=12)

    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


if __name__ == "__main__":
    main()
