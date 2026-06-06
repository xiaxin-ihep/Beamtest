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

from siwecal_analysis.conversion import run_root_conversion, stage_raw_segments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage raw .bin files and convert them to ROOT with ConvertDirectorySL_Raw.cc.")
    parser.add_argument("--input-dir", type=Path, required=True, help="Directory containing .bin/.bin_XXXX files.")
    parser.add_argument("--run-name", help="Run name. Defaults to the input directory name.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory that will contain converted ROOT files.")
    parser.add_argument("--macro-path", type=Path, default=Path("/Users/xiaxin/Desktop/work/TB_Desy/ConvertDirectorySL_Raw.cc"))
    parser.add_argument("--copy-raw", action="store_true", help="Copy raw files instead of creating symlinks in the staging directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_name = args.run_name or args.input_dir.name
    stage_dir = args.output_dir / "raw_stage"
    staged_files = stage_raw_segments(args.input_dir, stage_dir, run_name, copy_files=args.copy_raw)
    run_root_conversion(stage_dir, run_name, args.output_dir, args.macro_path)
    print(
        json.dumps(
            {
                "run_name": run_name,
                "staged_raw_dir": str(stage_dir),
                "staged_files": [str(path) for path in staged_files],
                "root_output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

