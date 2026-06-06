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

from siwecal_analysis.analysis import amplitude_map, mapped_channel_stats, snr_map
from siwecal_analysis.config import CONVERTER_DIR, DEFAULT_ECAL_MAPPING, DEFAULT_OUTPUT_DIR
from siwecal_analysis.io import find_run_directory, load_layer
from siwecal_analysis.mapping import load_ecal_mapping
from siwecal_analysis.plotting import save_heatmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build signal/amplitude/SNR maps from a physics run.")
    parser.add_argument("--run", required=True)
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--memory", type=int, default=-1, help="Memory cell to analyze. Use -1 to merge all memories.")
    parser.add_argument("--converted-base", type=Path, default=CONVERTER_DIR)
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--pedestal-file", type=Path, help="Optional pedestal npz produced by analyze_pedestal.py.")
    parser.add_argument("--statistic", choices=["mean", "median"], default="mean")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "signal")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    memory = None if args.memory < 0 else args.memory
    run_dir = find_run_directory(args.converted_base, args.run)
    layer_data = load_layer(run_dir, args.layer)
    mapping = load_ecal_mapping(args.mapping_file)

    pedestal_channel_mean = None
    pedestal_channel_sigma = None
    if args.pedestal_file:
        pedestal_data = np.load(args.pedestal_file)
        pedestal_channel_mean = pedestal_data["channel_mean"]
        pedestal_channel_sigma = pedestal_data["channel_std"]

    channel_signal = amplitude_map(
        adc_high=layer_data.adc_high,
        pedestal_means=pedestal_channel_mean,
        hitbit_high=layer_data.hitbit_high,
        memory=memory,
        statistic=args.statistic,
    )
    signal_map = mapped_channel_stats(channel_signal, mapping)

    run_name = run_dir.name
    args.output_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, np.ndarray] = {
        "signal_map": signal_map,
        "channel_signal": channel_signal,
    }
    save_heatmap(signal_map, args.output_dir / f"{run_name}_layer{args.layer}_signal.png", f"{run_name} layer {args.layer} signal ({args.statistic})", cmap="magma")

    if pedestal_channel_sigma is not None:
        channel_snr = snr_map(channel_signal, pedestal_channel_sigma)
        snr_plot = mapped_channel_stats(channel_snr, mapping)
        payload["snr_map"] = snr_plot
        payload["channel_snr"] = channel_snr
        save_heatmap(snr_plot, args.output_dir / f"{run_name}_layer{args.layer}_snr.png", f"{run_name} layer {args.layer} S/N", cmap="plasma")

    np.savez(args.output_dir / f"{run_name}_layer{args.layer}_signal.npz", **payload)
    print(json.dumps({"run_dir": str(run_dir), "output": str(args.output_dir)}, indent=2))


if __name__ == "__main__":
    main()
