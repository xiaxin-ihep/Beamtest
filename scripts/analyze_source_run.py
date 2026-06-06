#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
SORT_DIR = SCRIPT_DIR.parent
os.environ.setdefault("MPLCONFIGDIR", str(SORT_DIR / ".mplconfig"))
if str(SORT_DIR) not in sys.path:
    sys.path.insert(0, str(SORT_DIR))

from siwecal_analysis.config import DEFAULT_ECAL_MAPPING, DEFAULT_OUTPUT_DIR
from siwecal_analysis.io import load_layer
from siwecal_analysis.source_analysis import analyze_source_layer, parse_run_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze one ECAL-alone source run layer and produce source maps/histograms.")
    parser.add_argument("--run-dir", type=Path, required=True, help="Converted run directory containing ROOT and/or decoupechannel files.")
    parser.add_argument("--layer", type=int, default=0, help="Layer index to analyze.")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "source")
    parser.add_argument("--settings-file", type=Path, help="Optional Run_Settings.txt file to include in the summary JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    layer_data = load_layer(args.run_dir, args.layer, include_trig=True)
    metadata = parse_run_settings(args.settings_file) if args.settings_file else {}
    summary = analyze_source_layer(
        adc_high=layer_data.adc_high,
        hitbit_high=layer_data.hitbit_high,
        adc_trig=layer_data.adc_trig,
        mapping_file=args.mapping_file,
        output_dir=args.output_dir,
        run_name=args.run_dir.name,
        layer=args.layer,
        metadata=metadata,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

