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
from siwecal_analysis.source_analysis import analyze_hits_histogram_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a quick hit map directly from DAQ hitsHistogram.txt.")
    parser.add_argument("--histogram-file", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--layer", type=int, default=0)
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "hitsHistogram")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = analyze_hits_histogram_file(
        histogram_file=args.histogram_file,
        mapping_file=args.mapping_file,
        output_dir=args.output_dir,
        run_name=args.run_name,
        layer=args.layer,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
