from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def save_heatmap(
    data: np.ndarray,
    output: str | Path,
    title: str,
    cmap: str = "viridis",
    xlabel: str = "x index",
    ylabel: str = "y index",
    label_fontsize: int = 12,
    title_fontsize: int = 14,
) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    masked = np.ma.masked_invalid(data)
    masked = np.ma.masked_where(masked == 0, masked)

    fig, ax = plt.subplots(figsize=(8, 8))
    image = ax.imshow(masked, cmap=cmap, origin="lower", interpolation="nearest")
    ax.set_title(title, fontsize=title_fontsize)
    ax.set_xlabel(xlabel, fontsize=label_fontsize)
    ax.set_ylabel(ylabel, fontsize=label_fontsize)
    ax.tick_params(axis="both", labelsize=max(label_fontsize - 4, 10))
    fig.colorbar(image, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def save_curve(
    x: list[float] | np.ndarray,
    y: list[float] | np.ndarray,
    output: str | Path,
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x, y, marker="o", linewidth=2)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)
