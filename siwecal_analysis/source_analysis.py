from __future__ import annotations

from pathlib import Path
import json
import re

import matplotlib.pyplot as plt
import numpy as np

from .analysis import amplitude_map, hit_count_map, mapped_channel_stats
from .mapping import load_ecal_mapping
from .plotting import save_heatmap


def format_source_plot_title(run_name: str) -> str:
    match = re.search(r"source_asu_(\d{4})_(\d{3})_th(\d+)", run_name)
    if match:
        return f"Source_test_{match.group(1)}_{match.group(2)}_th{match.group(3)}"
    return run_name


def parse_run_settings(settings_file: str | Path) -> dict[str, str | int | float]:
    settings_file = Path(settings_file)
    if not settings_file.exists():
        return {}

    text = settings_file.read_text(errors="ignore")
    patterns = {
        "trigger_type": r"TriggerType:\s*(\d+)",
        "acq_window_ms": r"ACQWindow:\s*(\d+)",
        "connected_asus": r"Nb_Of_Connected_ASUs:\s*(\d+)",
        "threshold_dac": r"ThresholdDAC:\s*(\d+)",
        "hold_delay": r"HoldDelay:\s*(\d+)",
        "feedback_cap": r"FeedbackCap:\s*(\d+)",
    }

    metadata: dict[str, str | int | float] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            metadata[key] = int(match.group(1))
    return metadata


def parse_hits_histogram(histogram_file: str | Path) -> dict[str, object]:
    histogram_file = Path(histogram_file)
    text = histogram_file.read_text(errors="ignore").splitlines()

    saturation_rate = None
    channel_hits = np.zeros((16, 64), dtype=float)
    for line in text:
        if line.startswith("SlabIndex") and "SaturationRate" in line:
            match = re.search(r"SaturationRate \(per cent\)\s+([0-9.]+)", line)
            if match:
                saturation_rate = float(match.group(1))
        if "ChipId" in line and "Channel" in line and "TotalNbOfHits" in line:
            match = re.search(r"ChipId\s+(\d+)\s+Channel\s+(\d+)\s+TotalNbOfHits\s+(\d+)", line)
            if match:
                chip_id = int(match.group(1))
                channel_id = int(match.group(2))
                hits = int(match.group(3))
                if chip_id < 16 and channel_id < 64:
                    channel_hits[chip_id, channel_id] = hits

    return {
        "saturation_rate_percent": saturation_rate,
        "channel_hits": channel_hits,
    }


def save_histogram(samples: np.ndarray, output: str | Path, title: str, xlabel: str) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.hist(samples, bins=200, histtype="stepfilled", alpha=0.75)
    ax.set_title(title, fontsize=22)
    ax.set_xlabel(xlabel, fontsize=20)
    ax.set_ylabel("Entries", fontsize=20)
    ax.tick_params(axis="both", labelsize=16)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def analyze_source_layer(
    adc_high: np.ndarray,
    hitbit_high: np.ndarray,
    mapping_file: str | Path,
    output_dir: str | Path,
    run_name: str,
    layer: int,
    adc_trig: np.ndarray | None = None,
    metadata: dict[str, str | int | float] | None = None,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mapping = load_ecal_mapping(mapping_file)
    plot_title = format_source_plot_title(run_name)

    n_windows, _, n_memories, _ = adc_high.shape
    channel_hits = hit_count_map(hitbit_high, memory=None)
    hit_map = mapped_channel_stats(channel_hits, mapping)
    hit_fraction = channel_hits / float(n_windows * n_memories)
    hit_fraction_map = mapped_channel_stats(hit_fraction, mapping)

    channel_signal = amplitude_map(adc_high=adc_high, hitbit_high=hitbit_high, memory=None, statistic="mean")
    signal_map = mapped_channel_stats(channel_signal, mapping)

    payload: dict[str, np.ndarray] = {
        "channel_hits": channel_hits,
        "hit_map": hit_map,
        "channel_hit_fraction": hit_fraction,
        "hit_fraction_map": hit_fraction_map,
        "channel_signal_mean": channel_signal,
        "signal_map": signal_map,
    }

    save_heatmap(
        hit_map,
        output_dir / f"{run_name}_layer{layer}_source_hit_counts.pdf",
        plot_title,
        cmap="YlOrBr",
        label_fontsize=20,
        title_fontsize=22,
    )
    save_heatmap(
        hit_fraction_map,
        output_dir / f"{run_name}_layer{layer}_source_hit_fraction.pdf",
        plot_title,
        cmap="viridis",
        label_fontsize=20,
        title_fontsize=22,
    )
    save_heatmap(
        signal_map,
        output_dir / f"{run_name}_layer{layer}_source_signal_mean.pdf",
        plot_title,
        cmap="magma",
        label_fontsize=20,
        title_fontsize=22,
    )

    triggered_adc = adc_high[hitbit_high == 1]
    if triggered_adc.size > 0:
        save_histogram(
            triggered_adc.astype(float),
            output_dir / f"{run_name}_layer{layer}_triggered_adc_hist.pdf",
            plot_title,
            "ADC high",
        )

    if adc_trig is not None:
        trig_mean = np.mean(adc_trig, axis=(0, 2))
        trig_map = mapped_channel_stats(trig_mean, mapping)
        payload["channel_adc_trig_mean"] = trig_mean
        payload["adc_trig_mean_map"] = trig_map
        save_heatmap(
            trig_map,
            output_dir / f"{run_name}_layer{layer}_adc_trig_mean.pdf",
            plot_title,
            cmap="cividis",
            label_fontsize=20,
            title_fontsize=22,
        )

    flat_hits = channel_hits.reshape(-1)
    order = np.argsort(flat_hits)[::-1]
    top_channels: list[dict[str, int | float]] = []
    for index in order[:20]:
        chip_id = int(index // 64)
        channel_id = int(index % 64)
        top_channels.append(
            {
                "chip": chip_id,
                "channel": channel_id,
                "hits": int(channel_hits[chip_id, channel_id]),
                "hit_fraction": float(hit_fraction[chip_id, channel_id]),
                "signal_mean": float(channel_signal[chip_id, channel_id]),
            }
        )

    np.savez(output_dir / f"{run_name}_layer{layer}_source_summary.npz", **payload)

    summary = {
        "run_name": run_name,
        "layer": layer,
        "n_windows": int(n_windows),
        "n_memories": int(n_memories),
        "total_triggered_samples": int(np.sum(channel_hits)),
        "top_channels": top_channels,
    }
    if metadata:
        summary["run_settings"] = metadata

    with (output_dir / f"{run_name}_layer{layer}_source_summary.json").open("w") as handle:
        json.dump(summary, handle, indent=2)

    return summary


def analyze_hits_histogram_file(
    histogram_file: str | Path,
    mapping_file: str | Path,
    output_dir: str | Path,
    run_name: str,
    layer: int = 0,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mapping = load_ecal_mapping(mapping_file)
    parsed = parse_hits_histogram(histogram_file)
    channel_hits = parsed["channel_hits"]
    hit_map = mapped_channel_stats(channel_hits, mapping)
    plot_title = format_source_plot_title(run_name)

    save_heatmap(
        hit_map,
        output_dir / f"{run_name}_layer{layer}_hitsHistogram_map.pdf",
        plot_title,
        cmap="YlOrBr",
        label_fontsize=20,
        title_fontsize=22,
    )
    np.savez(output_dir / f"{run_name}_layer{layer}_hitsHistogram.npz", channel_hits=channel_hits, hit_map=hit_map)

    flat_hits = channel_hits.reshape(-1)
    order = np.argsort(flat_hits)[::-1]
    top_channels: list[dict[str, int | float]] = []
    for index in order[:20]:
        chip_id = int(index // 64)
        channel_id = int(index % 64)
        top_channels.append(
            {
                "chip": chip_id,
                "channel": channel_id,
                "hits": int(channel_hits[chip_id, channel_id]),
            }
        )

    summary = {
        "run_name": run_name,
        "layer": layer,
        "saturation_rate_percent": parsed["saturation_rate_percent"],
        "top_channels": top_channels,
    }
    with (output_dir / f"{run_name}_layer{layer}_hitsHistogram_summary.json").open("w") as handle:
        json.dump(summary, handle, indent=2)
    return summary
