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
from siwecal_analysis.conversion import convert_root_to_decoupechannel, run_root_conversion, stage_raw_segments
from siwecal_analysis.io import load_layer
from siwecal_analysis.source_analysis import analyze_source_layer, parse_run_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full source-run pipeline: binary -> ROOT -> decoupechannel npy -> source plots.")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing the original source run files.")
    parser.add_argument("--run-name", help="Run name. Defaults to the input directory name.")
    parser.add_argument("--layer", type=int, default=0, help="Single layer index to analyze for this ECAL-alone test.")
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "pipeline", help="Pipeline working directory.")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--macro-path", type=Path, default=Path("/Users/xiaxin/Desktop/work/TB_Desy/ConvertDirectorySL_Raw.cc"))
    parser.add_argument("--copy-raw", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_name = args.run_name or args.input_dir.name
    run_work_dir = args.work_dir / run_name
    root_dir = run_work_dir / "converted"
    stage_dir = run_work_dir / "raw_stage"
    analysis_dir = run_work_dir / "analysis"

    staged_files = stage_raw_segments(args.input_dir, stage_dir, run_name, copy_files=args.copy_raw)
    run_root_conversion(stage_dir, run_name, root_dir, args.macro_path)
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
                "staged_files": [str(path) for path in staged_files],
                "root_dir": str(root_dir),
                "analysis_dir": str(analysis_dir),
                "summary": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

