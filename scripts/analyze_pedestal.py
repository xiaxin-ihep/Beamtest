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

from siwecal_analysis.analysis import channelwise_gaussian_stats, mapped_channel_stats
from siwecal_analysis.config import CONVERTER_DIR, DEFAULT_ECAL_MAPPING, DEFAULT_OUTPUT_DIR
from siwecal_analysis.io import find_run_directory, load_layer
from siwecal_analysis.mapping import load_ecal_mapping
from siwecal_analysis.plotting import save_heatmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build pedestal mean/sigma maps from decoupechannel arrays.")
    parser.add_argument("--run", required=True, help="Run number or run directory suffix, for example 647 or 090647.")
    parser.add_argument("--layer", type=int, required=True, help="Layer index, for example 0/1/2.")
    parser.add_argument("--memory", type=int, default=0, help="Memory cell to analyze. Use -1 to merge all memories.")
    parser.add_argument("--converted-base", type=Path, default=CONVERTER_DIR, help="Base directory that contains converted runs.")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING, help="ECAL mapping text file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "pedestal", help="Output directory.")
    parser.add_argument("--min-entries", type=int, default=50, help="Minimum entries required for a channel fit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    memory = None if args.memory < 0 else args.memory
    run_dir = find_run_directory(args.converted_base, args.run)
    layer_data = load_layer(run_dir, args.layer)
    mapping = load_ecal_mapping(args.mapping_file)

    stats = channelwise_gaussian_stats(
        adc_high=layer_data.adc_high,
        hitbit_high=layer_data.hitbit_high,
        use_hitbit=0,
        memory=memory,
        min_entries=args.min_entries,
    )
    mean_map = mapped_channel_stats(stats.mean, mapping)
    sigma_map = mapped_channel_stats(stats.sigma, mapping)
    count_map = mapped_channel_stats(stats.counts.astype(float), mapping)

    run_name = run_dir.name
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.output_dir / f"{run_name}_layer{args.layer}_pedestal.npz",
        mean=mean_map,
        std=sigma_map,
        count=count_map,
        channel_mean=stats.mean,
        channel_std=stats.sigma,
        channel_count=stats.counts,
    )
    save_heatmap(mean_map, args.output_dir / f"{run_name}_layer{args.layer}_pedestal_mean.png", f"{run_name} layer {args.layer} pedestal mean")
    save_heatmap(sigma_map, args.output_dir / f"{run_name}_layer{args.layer}_pedestal_sigma.png", f"{run_name} layer {args.layer} pedestal sigma")

    summary = {
        "run_dir": str(run_dir),
        "layer": args.layer,
        "memory": memory,
        "output": str(args.output_dir / f"{run_name}_layer{args.layer}_pedestal.npz"),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
