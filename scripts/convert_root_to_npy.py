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

from siwecal_analysis.conversion import convert_root_to_decoupechannel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert ROOT files in one run directory into decoupechannel .npy arrays.")
    parser.add_argument("--run-dir", type=Path, required=True, help="Directory that contains converted_*.root files.")
    parser.add_argument("--layers", nargs="*", type=int, help="Layers to export. Default: all layers in the ROOT tree.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    layer_paths = convert_root_to_decoupechannel(args.run_dir, layers=args.layers or None)
    print(
        json.dumps(
            {
                "run_dir": str(args.run_dir),
                "layers": {str(layer): str(path) for layer, path in sorted(layer_paths.items())},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

