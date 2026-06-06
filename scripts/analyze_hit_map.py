#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
SORT_DIR = SCRIPT_DIR.parent
os.environ.setdefault("MPLCONFIGDIR", str(SORT_DIR / ".mplconfig"))
if str(SORT_DIR) not in sys.path:
    sys.path.insert(0, str(SORT_DIR))

from siwecal_analysis.analysis import hit_count_map, mapped_channel_stats
from siwecal_analysis.config import CONVERTER_DIR, DEFAULT_ECAL_MAPPING, DEFAULT_OUTPUT_DIR
from siwecal_analysis.io import find_run_directory, load_layer
from siwecal_analysis.mapping import load_ecal_mapping
from siwecal_analysis.plotting import save_heatmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build hit-count maps from hitbit arrays.")
    parser.add_argument("--run", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--memory", type=int, default=-1, help="Memory cell to analyze. Use -1 to merge all memories.")
    parser.add_argument("--converted-base", type=Path, default=CONVERTER_DIR)
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "hitmap")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    memory = None if args.memory < 0 else args.memory
    run_dir = find_run_directory(args.converted_base, args.run)
    layer_data = load_layer(run_dir, args.layer)
    mapping = load_ecal_mapping(args.mapping_file)

    channel_hits = hit_count_map(layer_data.hitbit_high, memory=memory)
    hit_map = mapped_channel_stats(channel_hits, mapping)

    run_name = run_dir.name
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.output_dir / f"{run_name}_layer{args.layer}_hitmap.npz",
        hit_map=hit_map,
        channel_hits=channel_hits,
    )
    save_heatmap(hit_map, args.output_dir / f"{run_name}_layer{args.layer}_hitmap.png", f"{run_name} layer {args.layer} hit counts", cmap="YlOrBr")
    print(json.dumps({"run_dir": str(run_dir), "output": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
