from __future__ import annotations

from pathlib import Path


SORT_DIR = Path(__file__).resolve().parent.parent
LOCAL_ANALYSIS_DIR = SORT_DIR.parent
ANALYSIS_ROOT = LOCAL_ANALYSIS_DIR.parent.parent
MAPPING_DIR = ANALYSIS_ROOT / "mapping"
CONVERTER_DIR = ANALYSIS_ROOT / "converter_SLB" / "convertedfiles"
DEFAULT_OUTPUT_DIR = SORT_DIR / "output"

DEFAULT_ECAL_MAPPING = MAPPING_DIR / "fev10_chip_channel_x_y_mapping.txt"
DEFAULT_HCAL_MAPPING = MAPPING_DIR / "hcal_mapping.txt"

