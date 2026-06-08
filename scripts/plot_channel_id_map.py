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
    parser = argparse.ArgumentParser(description="Plot the channel-ID layout corresponding to the 32x32 hit map.")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR / "source_campaign" / "overview" / "channel_id_position_map.pdf")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mapping = load_ecal_mapping(args.mapping_file)

    channel_map = np.zeros((32, 32), dtype=int)
    for x in range(32):
        for y in range(32):
            channel_map[31 - y, 31 - x] = int(mapping[x, y, 1])

    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 11))
    image = ax.imshow(channel_map, origin="lower", cmap="viridis", interpolation="nearest", vmin=0, vmax=63)
    ax.set_title("Channel ID layout on the 32x32 hit map", fontsize=22)
    ax.set_xlabel("x index", fontsize=20)
    ax.set_ylabel("y index", fontsize=20)
    ax.tick_params(axis="both", labelsize=14)

    for y in range(32):
        for x in range(32):
            value = int(channel_map[y, x])
            ax.text(
                x,
                y,
                str(value),
                ha="center",
                va="center",
                fontsize=6.5,
                color="white" if value < 40 else "black",
            )

    for edge in [7.5, 15.5, 23.5]:
        ax.axvline(edge, color="white", linewidth=1.0, alpha=0.8)
        ax.axhline(edge, color="white", linewidth=1.0, alpha=0.8)

    cbar = fig.colorbar(image, ax=ax, shrink=0.88)
    cbar.set_label("Channel ID", fontsize=16)
    cbar.ax.tick_params(labelsize=12)

    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


if __name__ == "__main__":
    main()
