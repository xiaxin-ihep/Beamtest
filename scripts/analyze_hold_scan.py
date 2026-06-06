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

from siwecal_analysis.analysis import fit_channel_gaussian
from siwecal_analysis.config import CONVERTER_DIR, DEFAULT_OUTPUT_DIR
from siwecal_analysis.io import find_run_directory, load_layer
from siwecal_analysis.plotting import save_curve


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Perform a hold-value scan for one ECAL channel.")
    parser.add_argument("--runs", nargs="+", required=True, help="Runs ordered in the same way as the hold values.")
    parser.add_argument("--hold-values", nargs="+", required=True, type=float, help="Hold values in ns.")
    parser.add_argument("--layer", type=int, required=True)
    parser.add_argument("--chip", type=int, required=True)
    parser.add_argument("--channel", type=int, required=True)
    parser.add_argument("--memory", type=int, default=0)
    parser.add_argument("--converted-base", type=Path, default=CONVERTER_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "hold_scan")
    parser.add_argument("--use-hitbit", type=int, default=1, choices=[0, 1], help="Use hitbit==1 for signal or hitbit==0 for pedestal.")
    parser.add_argument("--min-entries", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if len(args.runs) != len(args.hold_values):
        raise SystemExit("--runs and --hold-values must have the same length")

    means: list[float] = []
    sigmas: list[float] = []
    entries: list[int] = []
    run_names: list[str] = []

    for run in args.runs:
        run_dir = find_run_directory(args.converted_base, run)
        layer_data = load_layer(run_dir, args.layer)
        samples = layer_data.adc_high[:, args.chip, args.memory, args.channel]
        hitbits = layer_data.hitbit_high[:, args.chip, args.memory, args.channel]
        selected = samples[hitbits == args.use_hitbit]
        mean, sigma, count = fit_channel_gaussian(selected, min_entries=args.min_entries)
        means.append(mean)
        sigmas.append(sigma)
        entries.append(count)
        run_names.append(run_dir.name)

    tag = f"layer{args.layer}_chip{args.chip}_memory{args.memory}_channel{args.channel}"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    save_curve(args.hold_values, means, args.output_dir / f"{tag}_mean_vs_hold.png", f"{tag} mean vs hold", "Hold value [ns]", "Gaussian mean [ADC]")
    save_curve(args.hold_values, sigmas, args.output_dir / f"{tag}_sigma_vs_hold.png", f"{tag} sigma vs hold", "Hold value [ns]", "Gaussian sigma [ADC]")

    np.savez(
        args.output_dir / f"{tag}_hold_scan.npz",
        hold_values=np.array(args.hold_values, dtype=float),
        means=np.array(means, dtype=float),
        sigmas=np.array(sigmas, dtype=float),
        entries=np.array(entries, dtype=int),
        runs=np.array(run_names),
    )

    print(
        json.dumps(
            {
                "runs": run_names,
                "hold_values": args.hold_values,
                "means": means,
                "sigmas": sigmas,
                "entries": entries,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
