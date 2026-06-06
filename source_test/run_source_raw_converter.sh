#!/usr/bin/env bash
set -eo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <input-dir>"
  exit 1
fi

INPUT_DIR="$1"
RUN_NAME="$(basename "${INPUT_DIR}")"

source /Users/xiaxin/anaconda3/etc/profile.d/conda.sh
conda activate r6.28

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python "${SCRIPT_DIR}/../scripts/convert_source_binary_to_root.py" \
  --input-dir "${INPUT_DIR}" \
  --run-name "${RUN_NAME}" \
  --output-root "${SCRIPT_DIR}/../output/source_raw/${RUN_NAME}/${RUN_NAME}_source_raw.root"
