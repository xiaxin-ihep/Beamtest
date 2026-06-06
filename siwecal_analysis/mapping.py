from __future__ import annotations

from pathlib import Path

import numpy as np


def load_ecal_mapping(mapping_file: str | Path) -> np.ndarray:
    mapping_data = np.loadtxt(mapping_file, skiprows=1)
    x_order = np.argsort(mapping_data[:, 4])
    mapping_data = mapping_data[x_order]
    mapping = np.empty((32, 32, 2), dtype=int)
    for x in range(32):
        chunk = mapping_data[32 * x : 32 * (x + 1)]
        y_order = np.argsort(chunk[:, 5])
        mapping[x, :, :] = chunk[y_order][:, [0, 3]]
    return mapping


def channel_matrix_to_map(data: np.ndarray, mapping: np.ndarray) -> np.ndarray:
    if data.shape != (16, 64):
        raise ValueError(f"Expected (16, 64) matrix, got {data.shape}")

    mapped = np.zeros((32, 32), dtype=float)
    for x in range(32):
        for y in range(32):
            chip_id, channel_id = mapping[x, y]
            mapped[31 - y, 31 - x] = data[chip_id, channel_id]
    return mapped

