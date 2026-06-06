#!/usr/bin/env bash
set -eo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <input-dir> [layer]"
  exit 1
fi

INPUT_DIR="$1"
LAYER="${2:-0}"

source /Users/xiaxin/anaconda3/etc/profile.d/conda.sh
conda activate r6.28

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python "${SCRIPT_DIR}/scripts/run_source_pipeline.py" \
  --input-dir "${INPUT_DIR}" \
  --layer "${LAYER}"
