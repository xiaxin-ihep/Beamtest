from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np


RUN_PATTERN = re.compile(r"(\d{3,6})$")


def _as_run_tag(run: str | int) -> str:
    text = str(run)
    match = RUN_PATTERN.search(text)
    if match:
        digits = match.group(1)
        if len(digits) <= 3:
            return f"090{digits.zfill(3)}"
        if len(digits) == 4 and digits.startswith("0"):
            return f"09{digits}"
        if len(digits) == 5:
            return f"0{digits}"
        return digits
    return text


def find_run_directory(base_dir: str | Path, run: str | int) -> Path:
    base_dir = Path(base_dir)
    run_tag = _as_run_tag(run)
    candidates = sorted(base_dir.glob(f"*{run_tag}"))
    if not candidates:
        raise FileNotFoundError(f"Could not find run directory matching '*{run_tag}' under {base_dir}")
    if len(candidates) > 1:
        exact_suffix = [path for path in candidates if path.name.endswith(run_tag)]
        if len(exact_suffix) == 1:
            return exact_suffix[0]
    return candidates[0]


@dataclass
class LayerData:
    adc_high: np.ndarray
    hitbit_high: np.ndarray
    adc_trig: np.ndarray | None = None


def _root_file_from_run_dir(run_dir: Path) -> Path:
    root_files = sorted(run_dir.glob("*.root"))
    if not root_files:
        raise FileNotFoundError(f"No ROOT file found under {run_dir}")
    return root_files[0]


def load_layer_from_root(run_dir: str | Path, layer: int) -> LayerData:
    try:
        import uproot
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "ROOT-only runs require the 'uproot' Python package. "
            "Either install uproot or convert the run to decoupechannel .npy arrays first."
        ) from exc

    run_dir = Path(run_dir)
    root_file = _root_file_from_run_dir(run_dir)
    with uproot.open(root_file) as handle:
        tree = handle["siwecaldecoded"]
        arrays = tree.arrays(["adc_high", "hitbit_high"], library="np")

    adc_high = arrays["adc_high"][:, layer, :, :, :]
    hitbit_high = arrays["hitbit_high"][:, layer, :, :, :]
    return LayerData(adc_high=adc_high, hitbit_high=hitbit_high)


def load_layer_from_decoupechannel(
    run_dir: str | Path,
    layer: int,
    include_trig: bool = False,
) -> LayerData:
    layer_dir = Path(run_dir) / "decoupechannel" / f"layer{layer}"
    if not layer_dir.exists():
        raise FileNotFoundError(f"Layer directory not found: {layer_dir}")

    adc_sample = np.load(layer_dir / "adc_high_array0.npy")
    windows, chips, memories = adc_sample.shape
    adc_high = np.empty((windows, chips, memories, 64), dtype=adc_sample.dtype)
    hitbit_high = np.empty((windows, chips, memories, 64), dtype=np.load(layer_dir / "hitbit_high_array0.npy").dtype)
    trig_sample = layer_dir / "adc_trig_array0.npy"
    adc_trig = np.empty((windows, chips, memories, 64), dtype=np.load(trig_sample).dtype) if include_trig and trig_sample.exists() else None

    for channel in range(64):
        adc_high[:, :, :, channel] = np.load(layer_dir / f"adc_high_array{channel}.npy")
        hitbit_high[:, :, :, channel] = np.load(layer_dir / f"hitbit_high_array{channel}.npy")
        if adc_trig is not None:
            adc_trig[:, :, :, channel] = np.load(layer_dir / f"adc_trig_array{channel}.npy")

    return LayerData(adc_high=adc_high, hitbit_high=hitbit_high, adc_trig=adc_trig)


def load_layer(run_dir: str | Path, layer: int, include_trig: bool = False) -> LayerData:
    run_dir = Path(run_dir)
    layer_dir = run_dir / "decoupechannel" / f"layer{layer}"
    if layer_dir.exists():
        return load_layer_from_decoupechannel(run_dir, layer, include_trig=include_trig)
    return load_layer_from_root(run_dir, layer)
