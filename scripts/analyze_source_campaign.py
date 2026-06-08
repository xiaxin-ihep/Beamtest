#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = SCRIPT_DIR.parent
os.environ.setdefault("MPLCONFIGDIR", str(ANALYSIS_DIR / ".mplconfig"))
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from siwecal_analysis.config import DEFAULT_ECAL_MAPPING, DEFAULT_OUTPUT_DIR
from siwecal_analysis.source_campaign import analyze_source_campaign


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch source-test campaign analysis from hitsHistogram files.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR / "source_campaign")
    parser.add_argument("--mapping-file", type=Path, default=DEFAULT_ECAL_MAPPING)
    parser.add_argument("--layer", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = analyze_source_campaign(
        input_dir=args.input_dir,
        mapping_file=args.mapping_file,
        output_dir=args.output_dir,
        layer=args.layer,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
