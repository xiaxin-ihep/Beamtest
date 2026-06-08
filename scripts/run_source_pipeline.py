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
from siwecal_analysis.conversion import convert_root_to_decoupechannel, convert_source_binary_to_root
from siwecal_analysis.io import load_layer
from siwecal_analysis.source_analysis import analyze_source_layer, parse_run_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full source-run pipeline: decoded-frame source files -> siwecaldecoded ROOT -> decoupechannel npy -> source plots.")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing the original source run files.")
    parser.add_argument("--run-name", help="Run name. Defaults to the input directory name.")
    parser.add_argument("--layer", type=int, default=0, help="Single layer index to analyze for this ECAL-alone test.")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "pipeline", help="Pipeline working directory.")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_name = args.run_name or args.input_dir.name
    run_work_dir = args.work_dir / run_name
    root_dir = run_work_dir / "converted"
    analysis_dir = run_work_dir / "analysis"
    root_dir.mkdir(parents=True, exist_ok=True)
    output_root = root_dir / f"{run_name}_siwecaldecoded.root"

    conversion_summary = convert_source_binary_to_root(args.input_dir, output_root, run_name)
    convert_root_to_decoupechannel(root_dir, layers=[args.layer])

    layer_data = load_layer(root_dir, args.layer, include_trig=True)
    metadata = parse_run_settings(args.input_dir / "Run_Settings.txt")
    summary = analyze_source_layer(
        adc_high=layer_data.adc_high,
        hitbit_high=layer_data.hitbit_high,
        adc_trig=layer_data.adc_trig,
        mapping_file=args.mapping_file,
        output_dir=analysis_dir,
        run_name=run_name,
        layer=args.layer,
        metadata=metadata,
    )

    print(
        json.dumps(
            {
                "run_name": run_name,
                "input_dir": str(args.input_dir),
                "root_dir": str(root_dir),
                "root_file": str(output_root),
                "conversion": conversion_summary,
                "analysis_dir": str(analysis_dir),
                "summary": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
