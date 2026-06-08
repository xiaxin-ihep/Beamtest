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

from siwecal_analysis.conversion import convert_source_binary_to_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert source-test decoded frames (.bin/.bin_XXXX or .dat) into a beam-test-like siwecaldecoded ROOT tree.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--run-name", help="Defaults to input directory name.")
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_name = args.run_name or args.input_dir.name
    summary = convert_source_binary_to_root(args.input_dir, args.output_root, run_name)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
