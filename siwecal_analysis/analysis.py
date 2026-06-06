from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import curve_fit

from .mapping import channel_matrix_to_map


def gaussian(x: np.ndarray, mean: float, sigma: float, amplitude: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((x - mean) / sigma) ** 2)


@dataclass
class ChannelStats:
    mean: np.ndarray
    sigma: np.ndarray
    counts: np.ndarray


def apply_channel_mask(
    data: np.ndarray,
    exclude_channels: list[int] | None = None,
    exclude_pairs: list[tuple[int, int]] | None = None,
) -> np.ndarray:
    masked = data.copy()
    if exclude_channels:
        masked[:, :, :, exclude_channels] = 0
    if exclude_pairs:
        for chip_id, channel_id in exclude_pairs:
            masked[:, chip_id, :, channel_id] = 0
    return masked


def extract_pedestal_samples(adc_high: np.ndarray, hitbit_high: np.ndarray) -> np.ndarray:
    return np.where(hitbit_high == 0, adc_high, 0)


def extract_signal_samples(adc_high: np.ndarray, hitbit_high: np.ndarray) -> np.ndarray:
    return np.where(hitbit_high == 1, adc_high, 0)


def _robust_range(samples: np.ndarray, nsigma: float = 3.0) -> np.ndarray:
    if samples.size == 0:
        return samples
    mean = float(np.mean(samples))
    sigma = float(np.std(samples))
    if sigma == 0:
        return samples
    return samples[(samples > mean - nsigma * sigma) & (samples < mean + nsigma * sigma)]


def fit_channel_gaussian(
    samples: np.ndarray,
    min_entries: int = 50,
    bins: np.ndarray | None = None,
) -> tuple[float, float, int]:
    cleaned = samples[np.isfinite(samples)]
    cleaned = cleaned[cleaned != 0]
    if cleaned.size < min_entries:
        return 0.0, 0.0, int(cleaned.size)

    filtered = _robust_range(cleaned)
    if filtered.size < min_entries:
        return 0.0, 0.0, int(filtered.size)

    if bins is None:
        low = int(np.floor(np.min(filtered)))
        high = int(np.ceil(np.max(filtered))) + 1
        if high <= low:
            return float(np.mean(filtered)), float(np.std(filtered)), int(filtered.size)
        bins = np.arange(low, high, 1)

    counts, edges = np.histogram(filtered, bins=bins)
    if counts.sum() == 0:
        return 0.0, 0.0, int(filtered.size)

    centers = 0.5 * (edges[:-1] + edges[1:])
    mean_guess = float(np.mean(filtered))
    sigma_guess = max(float(np.std(filtered)), 1e-6)
    amp_guess = float(np.max(counts))
    lower = [float(np.min(filtered)), 0.0, 0.0]
    upper = [float(np.max(filtered)), sigma_guess * 5.0 + 1.0, amp_guess * 5.0 + 1.0]

    try:
        params, _ = curve_fit(
            gaussian,
            centers,
            counts,
            p0=[mean_guess, sigma_guess, amp_guess],
            bounds=(lower, upper),
            maxfev=20000,
        )
        return float(params[0]), float(abs(params[1])), int(filtered.size)
    except Exception:
        return mean_guess, sigma_guess, int(filtered.size)


def channelwise_gaussian_stats(
    adc_high: np.ndarray,
    hitbit_high: np.ndarray,
    use_hitbit: int,
    memory: int | None = 0,
    min_entries: int = 50,
    bins: np.ndarray | None = None,
) -> ChannelStats:
    if adc_high.shape != hitbit_high.shape:
        raise ValueError("adc_high and hitbit_high must share the same shape")

    means = np.zeros((16, 64), dtype=float)
    sigmas = np.zeros((16, 64), dtype=float)
    counts = np.zeros((16, 64), dtype=int)

    if memory is None:
        adc_view = adc_high
        hit_view = hitbit_high
    else:
        adc_view = adc_high[:, :, memory : memory + 1, :]
        hit_view = hitbit_high[:, :, memory : memory + 1, :]

    for chip_id in range(16):
        for channel_id in range(64):
            samples = adc_view[:, chip_id, :, channel_id][hit_view[:, chip_id, :, channel_id] == use_hitbit]
            mean, sigma, n = fit_channel_gaussian(samples, min_entries=min_entries, bins=bins)
            means[chip_id, channel_id] = mean
            sigmas[chip_id, channel_id] = sigma
            counts[chip_id, channel_id] = n
    return ChannelStats(mean=means, sigma=sigmas, counts=counts)


def hit_count_map(hitbit_high: np.ndarray, memory: int | None = None) -> np.ndarray:
    if memory is None:
        hits = np.sum(hitbit_high == 1, axis=(0, 2))
    else:
        hits = np.sum(hitbit_high[:, :, memory, :] == 1, axis=0)
    return hits.astype(float)


def amplitude_map(
    adc_high: np.ndarray,
    pedestal_means: np.ndarray | None = None,
    hitbit_high: np.ndarray | None = None,
    memory: int | None = None,
    statistic: str = "mean",
) -> np.ndarray:
    if memory is None:
        values = adc_high
        hits = hitbit_high
    else:
        values = adc_high[:, :, memory : memory + 1, :]
        hits = hitbit_high[:, :, memory : memory + 1, :] if hitbit_high is not None else None

    if hits is not None:
        values = np.where(hits == 1, values, np.nan)
    else:
        values = values.astype(float)
        values[values == 0] = np.nan

    if pedestal_means is not None:
        pedestal = pedestal_means[np.newaxis, :, np.newaxis, :]
        values = values - pedestal

    if statistic == "mean":
        return np.nanmean(values, axis=(0, 2))
    if statistic == "median":
        return np.nanmedian(values, axis=(0, 2))
    raise ValueError(f"Unsupported statistic: {statistic}")


def snr_map(signal_means: np.ndarray, pedestal_sigmas: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        snr = np.divide(signal_means, pedestal_sigmas, out=np.zeros_like(signal_means), where=pedestal_sigmas > 0)
    return snr


def mapped_channel_stats(channel_matrix: np.ndarray, mapping: np.ndarray) -> np.ndarray:
    return channel_matrix_to_map(channel_matrix, mapping)

