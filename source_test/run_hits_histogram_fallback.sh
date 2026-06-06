#!/usr/bin/env bash
set -eo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <input-dir> [layer]"
  exit 1
fi

INPUT_DIR="$1"
LAYER="${2:-0}"
RUN_NAME="$(basename "${INPUT_DIR}")"

source /Users/xiaxin/anaconda3/etc/profile.d/conda.sh
conda activate r6.28

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python "${SCRIPT_DIR}/../scripts/analyze_hits_histogram.py" \
  --histogram-file "${INPUT_DIR}/hitsHistogram.txt" \
  --run-name "${RUN_NAME}" \
  --layer "${LAYER}" \
  --output-dir "${SCRIPT_DIR}/../output/hitsHistogram/${RUN_NAME}"

