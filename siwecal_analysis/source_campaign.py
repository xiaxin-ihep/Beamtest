from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import json
import math
import re

import matplotlib.pyplot as plt
import numpy as np

from .analysis import mapped_channel_stats
from .mapping import load_ecal_mapping
from .plotting import save_heatmap
from .source_analysis import parse_hits_histogram, parse_run_settings


@dataclass
class SourceRunResult:
    run_name: str
    asu_label: str
    threshold_dac: int | None
    hold_delay: int | None
    saturation_rate_percent: float | None
    total_hits: float
    alive_channel_fraction: float
    dead_channel_count: int
    quiet_channel_count: int
    hot_channel_count: int
    chip_total_mean: float
    chip_total_std: float
    chip_uniformity_cv: float
    region_uniformity_cv: float
    max_chip_hits: float
    min_chip_hits: float


def normalize_run_name(run_name: str) -> str:
    return run_name.lower().replace("-", "_")


def parse_run_identity(run_name: str, run_settings: dict[str, str | int | float]) -> dict[str, object]:
    normalized = normalize_run_name(run_name)
    asu_match = re.search(r"source_?asu_?(\d{4})_(\d{3})", normalized)
    run_match = re.search(r"run_(\d+)", normalized)
    threshold_match = re.search(r"th(\d+)", normalized)

    year = asu_match.group(1) if asu_match else None
    asu = asu_match.group(2) if asu_match else None
    run_number = int(run_match.group(1)) if run_match else None
    threshold = int(threshold_match.group(1)) if threshold_match else None
    if threshold is None:
        threshold = _to_int(run_settings.get("threshold_dac"))

    if year and asu:
        asu_label = f"{year}_{asu}"
    else:
        asu_label = "unknown"

    return {
        "asu_year": year,
        "asu_index": asu,
        "asu_label": asu_label,
        "run_number": run_number,
        "threshold_dac": threshold,
    }


def make_source_title(run_name: str, run_settings: dict[str, str | int | float]) -> str:
    identity = parse_run_identity(run_name, run_settings)
    threshold = identity["threshold_dac"]
    if identity["asu_label"] != "unknown" and threshold is not None:
        return f"Source_test_{identity['asu_label']}_th{threshold}"
    return run_name


def parse_ascii_source_dat(dat_file: str | Path) -> dict[str, object]:
    dat_file = Path(dat_file)
    channel_hits = np.zeros((16, 64), dtype=float)
    event_counts = np.zeros(16, dtype=int)
    current_chip = None
    event_has_hits = set()

    pattern = re.compile(
        r"Ch\s+(\d+)\s+LG\s+\d+\s+(\d+)\s+\d+\s+HG\s+\d+\s+(\d+)\s+\d+"
    )

    for line in dat_file.read_text(errors="ignore").splitlines():
        if line.startswith("#0") or line.startswith("#"):
            match = re.search(r"ChipID\s+(\d+)", line)
            if match:
                current_chip = int(match.group(1))
            continue
        if line.startswith("##"):
            event_has_hits.clear()
            continue

        match = pattern.search(line)
        if not match or current_chip is None or current_chip >= 16:
            continue
        channel = int(match.group(1))
        low_hit = int(match.group(2))
        high_hit = int(match.group(3))
        if channel >= 64:
            continue
        if low_hit or high_hit:
            channel_hits[current_chip, channel] += 1.0
            event_has_hits.add(current_chip)
        if event_has_hits:
            for chip in event_has_hits:
                event_counts[chip] += 1
            event_has_hits.clear()

    return {
        "saturation_rate_percent": None,
        "channel_hits": channel_hits,
    }


def load_source_channel_hits(run_dir: str | Path) -> tuple[dict[str, object], dict[str, str | int | float]]:
    run_dir = Path(run_dir)
    settings = parse_run_settings(run_dir / "Run_Settings.txt")

    histogram_file = run_dir / "hitsHistogram.txt"
    if histogram_file.exists():
        return parse_hits_histogram(histogram_file), settings

    ascii_candidates = sorted(run_dir.glob("*.dat"))
    if ascii_candidates:
        return parse_ascii_source_dat(ascii_candidates[0]), settings

    raise FileNotFoundError(f"No hitsHistogram.txt or ASCII .dat file found in {run_dir}")


def compute_run_metrics(channel_hits: np.ndarray, hit_map: np.ndarray) -> dict[str, object]:
    positive_hits = channel_hits[channel_hits > 0]
    median_positive = float(np.median(positive_hits)) if positive_hits.size else 0.0
    quiet_threshold = 0.5 * median_positive
    hot_threshold = 1.5 * median_positive

    alive_mask = channel_hits > 0
    dead_mask = channel_hits == 0
    quiet_mask = (channel_hits > 0) & (channel_hits < quiet_threshold)
    hot_mask = channel_hits > hot_threshold

    chip_totals = np.sum(channel_hits, axis=1)
    chip_means = np.mean(channel_hits, axis=1)
    total_hits = float(np.sum(channel_hits))

    region_totals = quadrant_sums(hit_map)

    chip_mean = float(np.mean(chip_totals)) if chip_totals.size else 0.0
    chip_std = float(np.std(chip_totals)) if chip_totals.size else 0.0
    chip_cv = chip_std / chip_mean if chip_mean > 0 else 0.0

    region_mean = float(np.mean(region_totals)) if region_totals.size else 0.0
    region_std = float(np.std(region_totals)) if region_totals.size else 0.0
    region_cv = region_std / region_mean if region_mean > 0 else 0.0

    return {
        "total_hits": total_hits,
        "alive_channel_fraction": float(np.mean(alive_mask)),
        "dead_channel_count": int(np.sum(dead_mask)),
        "quiet_channel_count": int(np.sum(quiet_mask)),
        "hot_channel_count": int(np.sum(hot_mask)),
        "quiet_threshold": quiet_threshold,
        "hot_threshold": hot_threshold,
        "chip_totals": chip_totals,
        "chip_means": chip_means,
        "chip_total_mean": chip_mean,
        "chip_total_std": chip_std,
        "chip_uniformity_cv": chip_cv,
        "region_uniformity_cv": region_cv,
        "region_totals": region_totals,
    }


def quadrant_sums(hit_map: np.ndarray) -> np.ndarray:
    nx, ny = hit_map.shape
    mx = nx // 2
    my = ny // 2
    quadrants = [
        hit_map[:mx, :my],
        hit_map[:mx, my:],
        hit_map[mx:, :my],
        hit_map[mx:, my:],
    ]
    return np.array([float(np.nansum(q)) for q in quadrants], dtype=float)


def top_channels(channel_hits: np.ndarray, limit: int = 10) -> list[dict[str, object]]:
    flat = channel_hits.reshape(-1)
    order = np.argsort(flat)[::-1]
    top = []
    for index in order[:limit]:
        chip = int(index // 64)
        channel = int(index % 64)
        top.append(
            {
                "chip": chip,
                "channel": channel,
                "hits": int(channel_hits[chip, channel]),
            }
        )
    return top


def analyze_source_campaign(
    input_dir: str | Path,
    mapping_file: str | Path,
    output_dir: str | Path,
    layer: int = 0,
) -> dict[str, object]:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    single_run_dir = output_dir / "runs"
    overview_dir = output_dir / "overview"
    single_run_dir.mkdir(parents=True, exist_ok=True)
    overview_dir.mkdir(parents=True, exist_ok=True)

    mapping = load_ecal_mapping(mapping_file)
    run_dirs = sorted(path for path in input_dir.iterdir() if path.is_dir())

    summaries: list[SourceRunResult] = []
    all_run_payloads: list[dict[str, object]] = []

    for run_dir in run_dirs:
        parsed, settings = load_source_channel_hits(run_dir)
        channel_hits = parsed["channel_hits"]
        hit_map = mapped_channel_stats(channel_hits, mapping)
        identity = parse_run_identity(run_dir.name, settings)
        metrics = compute_run_metrics(channel_hits, hit_map)
        total_hits = float(metrics["total_hits"])
        if total_hits > 0:
            channel_fraction = channel_hits / total_hits
            fraction_map = hit_map / total_hits
        else:
            channel_fraction = np.zeros_like(channel_hits, dtype=float)
            fraction_map = np.zeros_like(hit_map, dtype=float)
        title = make_source_title(run_dir.name, settings)
        run_output_dir = single_run_dir / run_dir.name
        run_output_dir.mkdir(parents=True, exist_ok=True)

        save_heatmap(
            hit_map,
            run_output_dir / f"{run_dir.name}_layer{layer}_hitmap.pdf",
            title,
            cmap="YlOrBr",
            label_fontsize=20,
            title_fontsize=22,
        )
        save_heatmap(
            fraction_map,
            run_output_dir / f"{run_dir.name}_layer{layer}_fraction_map.pdf",
            title,
            cmap="viridis",
            label_fontsize=20,
            title_fontsize=22,
        )
        save_chip_bar_chart(
            metrics["chip_totals"],
            metrics["chip_means"],
            run_output_dir / f"{run_dir.name}_layer{layer}_chip_hits.pdf",
            title,
        )
        run_top_channels = top_channels(channel_hits, limit=12)
        save_top_channels_chart(
            run_top_channels,
            run_output_dir / f"{run_dir.name}_layer{layer}_top_channels.pdf",
            title,
        )
        write_top_channels_csv(
            run_top_channels,
            run_output_dir / f"{run_dir.name}_layer{layer}_top_channels.csv",
        )

        payload = {
            "run_name": run_dir.name,
            "title": title,
            "layer": layer,
            "run_settings": settings,
            "identity": identity,
            "saturation_rate_percent": parsed["saturation_rate_percent"],
            "top_channels": run_top_channels,
            "fraction_definition": "fraction map = channel hits / overall hits in the run",
            "metrics": serialize_metrics(metrics),
        }
        with (run_output_dir / f"{run_dir.name}_layer{layer}_summary.json").open("w") as handle:
            json.dump(payload, handle, indent=2)

        summaries.append(
            SourceRunResult(
                run_name=run_dir.name,
                asu_label=str(identity["asu_label"]),
                threshold_dac=_to_int(identity["threshold_dac"]),
                hold_delay=_to_int(settings.get("hold_delay")),
                saturation_rate_percent=_to_float(parsed["saturation_rate_percent"]),
                total_hits=float(metrics["total_hits"]),
                alive_channel_fraction=float(metrics["alive_channel_fraction"]),
                dead_channel_count=int(metrics["dead_channel_count"]),
                quiet_channel_count=int(metrics["quiet_channel_count"]),
                hot_channel_count=int(metrics["hot_channel_count"]),
                chip_total_mean=float(metrics["chip_total_mean"]),
                chip_total_std=float(metrics["chip_total_std"]),
                chip_uniformity_cv=float(metrics["chip_uniformity_cv"]),
                region_uniformity_cv=float(metrics["region_uniformity_cv"]),
                max_chip_hits=float(np.max(metrics["chip_totals"])),
                min_chip_hits=float(np.min(metrics["chip_totals"])),
            )
        )
        all_run_payloads.append(
            {
                "run_name": run_dir.name,
                "title": title,
                "asu_label": identity["asu_label"],
                "threshold_dac": identity["threshold_dac"],
                "hit_map": hit_map,
                "fraction_map": fraction_map,
                "channel_hits": channel_hits,
                "channel_fraction": channel_fraction,
                "saturation_rate_percent": parsed["saturation_rate_percent"],
            }
        )

    write_campaign_csv(summaries, overview_dir / "source_campaign_summary.csv")
    selected_summaries = select_threshold_250_summaries(summaries)
    selected_payloads = select_threshold_250_payloads(all_run_payloads)

    save_metric_bar_chart(
        selected_summaries,
        metric="saturation_rate_percent",
        ylabel="Saturation rate [%]",
        output=overview_dir / "campaign_saturation_rate.pdf",
        title="Source campaign saturation rate (th250)",
    )
    save_metric_bar_chart(
        selected_summaries,
        metric="alive_channel_fraction",
        ylabel="Alive channel fraction",
        output=overview_dir / "campaign_alive_channel_fraction.pdf",
        title="Source campaign alive channel fraction (th250)",
        scale=100.0,
        ylabel_suffix=" [%]",
    )
    save_hot_dead_quiet_chart(selected_summaries, overview_dir / "campaign_hot_dead_quiet_counts.pdf")
    save_metric_bar_chart(
        selected_summaries,
        metric="chip_uniformity_cv",
        ylabel="Chip uniformity CV",
        output=overview_dir / "campaign_chip_uniformity_cv.pdf",
        title="Source campaign chip uniformity (th250)",
    )
    save_metric_bar_chart(
        selected_summaries,
        metric="region_uniformity_cv",
        ylabel="Region uniformity CV",
        output=overview_dir / "campaign_region_uniformity_cv.pdf",
        title="Source campaign region uniformity (th250)",
    )
    save_overall_map_grid(selected_payloads, overview_dir / "campaign_all_run_maps.pdf")
    save_overall_map_grid(
        selected_payloads,
        overview_dir / "campaign_all_run_fraction_maps.pdf",
        value_key="fraction_map",
        cmap="viridis",
        figure_title="All ASU normalized hit maps at threshold DAC 250\nColor scale = channel hits / overall hits in the run",
        colorbar_label="Hit fraction",
    )
    save_threshold_dependence_plots(summaries, overview_dir)
    save_asu_comparison_maps(all_run_payloads, overview_dir)

    overview = {
        "n_runs": len(summaries),
        "n_runs_selected_th250": len(selected_summaries),
        "runs": [asdict(item) for item in summaries],
        "runs_selected_th250": [asdict(item) for item in selected_summaries],
    }
    with (overview_dir / "source_campaign_overview.json").open("w") as handle:
        json.dump(overview, handle, indent=2)
    return overview


def select_threshold_250_summaries(summaries: list[SourceRunResult]) -> list[SourceRunResult]:
    selected = [item for item in summaries if item.threshold_dac == 250]
    selected.sort(key=lambda item: item.asu_label)
    return selected


def select_threshold_250_payloads(run_payloads: list[dict[str, object]]) -> list[dict[str, object]]:
    selected = [item for item in run_payloads if item.get("threshold_dac") == 250]
    selected.sort(key=lambda item: str(item.get("asu_label")))
    return selected


def summary_label(item: SourceRunResult) -> str:
    return item.asu_label


def add_definition_box(ax: plt.Axes, text: str, fontsize: int = 11) -> None:
    ax.text(
        1.01,
        0.98,
        text,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=fontsize,
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "0.75", "boxstyle": "round,pad=0.3"},
    )


def save_chip_bar_chart(
    chip_totals: np.ndarray,
    chip_means: np.ndarray,
    output: str | Path,
    title: str,
) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    chips = np.arange(len(chip_totals))
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    axes[0].bar(chips, chip_totals, color="#c76d3a")
    axes[0].set_ylabel("Total hits", fontsize=18)
    axes[0].set_title(title, fontsize=22)
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].tick_params(axis="both", labelsize=14)

    axes[1].bar(chips, chip_means, color="#497c88")
    axes[1].set_xlabel("Chip ID", fontsize=18)
    axes[1].set_ylabel("Mean hits / channel", fontsize=18)
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].tick_params(axis="both", labelsize=14)

    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def save_top_channels_chart(top: list[dict[str, object]], output: str | Path, title: str) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    labels = [f"C{row['chip']}:Ch{row['channel']}" for row in top]
    values = [row["hits"] for row in top]
    positions = np.arange(len(top))

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh(positions, values, color="#7d5ba6")
    ax.set_yticks(positions, labels=labels)
    ax.invert_yaxis()
    ax.set_title(title, fontsize=22)
    ax.set_xlabel("Hits", fontsize=18)
    ax.tick_params(axis="both", labelsize=13)
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def write_top_channels_csv(rows: list[dict[str, object]], output: str | Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["chip", "channel", "hits"])
        writer.writeheader()
        writer.writerows(rows)


def write_campaign_csv(summaries: list[SourceRunResult], output: str | Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(summaries[0]).keys()) if summaries else []
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in summaries:
            writer.writerow(asdict(item))


def save_metric_bar_chart(
    summaries: list[SourceRunResult],
    metric: str,
    ylabel: str,
    output: str | Path,
    title: str,
    scale: float = 1.0,
    ylabel_suffix: str = "",
) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    labels = [summary_label(item) for item in summaries]
    values = []
    for item in summaries:
        value = getattr(item, metric)
        values.append(np.nan if value is None else float(value) * scale)

    positions = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(12, len(labels) * 1.2), 6.5))
    ax.bar(positions, values, color="#56747a")
    ax.set_xticks(positions, labels=labels, rotation=45, ha="right")
    ax.set_ylabel(ylabel + ylabel_suffix, fontsize=18)
    ax.set_title(title, fontsize=22)
    ax.tick_params(axis="both", labelsize=12)
    ax.grid(True, axis="y", alpha=0.25)
    definition = None
    if metric == "saturation_rate_percent":
        definition = "Definition:\nDAQ saturation rate read from hitsHistogram.txt"
    elif metric == "alive_channel_fraction":
        definition = "Definition:\nalive fraction = N(channels with hits > 0) / 1024"
    elif metric == "chip_uniformity_cv":
        definition = "Definition:\nchip uniformity CV = std(chip total hits) / mean(chip total hits)"
    elif metric == "region_uniformity_cv":
        definition = "Definition:\nregion uniformity CV = std(4 quadrant hit sums) / mean(4 quadrant hit sums)"
    if definition:
        add_definition_box(ax, definition)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def save_hot_dead_quiet_chart(summaries: list[SourceRunResult], output: str | Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    labels = [summary_label(item) for item in summaries]
    positions = np.arange(len(labels))
    dead = np.array([item.dead_channel_count for item in summaries], dtype=float)
    quiet = np.array([item.quiet_channel_count for item in summaries], dtype=float)
    hot = np.array([item.hot_channel_count for item in summaries], dtype=float)

    fig, ax = plt.subplots(figsize=(max(12, len(labels) * 1.2), 7))
    ax.bar(positions, dead, label="Dead", color="#b23a48")
    ax.bar(positions, quiet, bottom=dead, label="Quiet", color="#f4a259")
    ax.bar(positions, hot, bottom=dead + quiet, label="Hot", color="#5b8e7d")
    ax.set_xticks(positions, labels=labels, rotation=45, ha="right")
    ax.set_ylabel("Channel count", fontsize=18)
    ax.set_title("Hot / dead / quiet channels per run", fontsize=22)
    ax.tick_params(axis="both", labelsize=12)
    ax.legend(fontsize=12)
    ax.grid(True, axis="y", alpha=0.25)
    add_definition_box(
        ax,
        "Definitions:\n"
        "dead: hits = 0\n"
        "quiet: 0 < hits < 0.5 x median(positive hits)\n"
        "hot: hits > 1.5 x median(positive hits)",
    )
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)


def save_overall_map_grid(
    run_payloads: list[dict[str, object]],
    output: str | Path,
    value_key: str = "hit_map",
    cmap: str = "YlOrBr",
    figure_title: str = "All ASU hit maps at threshold DAC 250\nShown in ASU order; color scale = hit counts",
    colorbar_label: str = "Hit counts",
) -> None:
    if not run_payloads:
        return
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    n_runs = len(run_payloads)
    ncols = min(4, n_runs)
    nrows = int(math.ceil(n_runs / ncols))
    vmax = max(float(np.nanmax(item[value_key])) for item in run_payloads)

    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(5.6 * ncols + 1.8, 4.8 * nrows),
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes).reshape(nrows, ncols)
    image = None
    for ax, item in zip(axes.flatten(), run_payloads):
        masked = np.ma.masked_invalid(item[value_key])
        masked = np.ma.masked_where(masked == 0, masked)
        image = ax.imshow(masked, origin="lower", cmap=cmap, vmin=0, vmax=vmax)
        ax.set_title(str(item["asu_label"]), fontsize=16)
        ax.set_xlabel("x index", fontsize=12)
        ax.set_ylabel("y index", fontsize=12)
        ax.tick_params(axis="both", labelsize=10)
    for ax in axes.flatten()[len(run_payloads):]:
        ax.axis("off")
    if image is not None:
        cbar = fig.colorbar(image, ax=axes, location="right", shrink=0.9, pad=0.02)
        cbar.set_label(colorbar_label, fontsize=12)
    fig.suptitle(figure_title, fontsize=18)
    fig.savefig(output)
    plt.close(fig)


def save_asu_comparison_maps(run_payloads: list[dict[str, object]], output_dir: str | Path) -> None:
    output_dir = Path(output_dir)
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in run_payloads:
        grouped.setdefault(str(item["asu_label"]), []).append(item)

    for asu_label, items in grouped.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda row: (9999 if row["threshold_dac"] is None else row["threshold_dac"], row["run_name"]))
        vmax = max(float(np.nanmax(item["hit_map"])) for item in items)
        fig, axes = plt.subplots(1, len(items), figsize=(5 * len(items), 5))
        axes = np.atleast_1d(axes)
        image = None
        for ax, item in zip(axes, items):
            masked = np.ma.masked_invalid(item["hit_map"])
            masked = np.ma.masked_where(masked == 0, masked)
            image = ax.imshow(masked, origin="lower", cmap="YlOrBr", vmin=0, vmax=vmax)
            ax.set_title(item["title"], fontsize=14)
            ax.set_xlabel("x index", fontsize=12)
            ax.set_ylabel("y index", fontsize=12)
            ax.tick_params(axis="both", labelsize=10)
        if image is not None:
            fig.colorbar(image, ax=axes.ravel().tolist(), shrink=0.8)
        fig.tight_layout()
        fig.savefig(output_dir / f"asu_{asu_label}_map_comparison.pdf")
        plt.close(fig)


def save_threshold_dependence_plots(summaries: list[SourceRunResult], output_dir: str | Path) -> None:
    output_dir = Path(output_dir)
    grouped: dict[str, list[SourceRunResult]] = {}
    for item in summaries:
        if item.threshold_dac is None:
            continue
        grouped.setdefault(item.asu_label, []).append(item)

    for asu_label, items in grouped.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda row: row.threshold_dac if row.threshold_dac is not None else -1)
        x = np.array([item.threshold_dac for item in items], dtype=float)
        y_sat = np.array([np.nan if item.saturation_rate_percent is None else item.saturation_rate_percent for item in items], dtype=float)
        y_alive = np.array([item.alive_channel_fraction * 100.0 for item in items], dtype=float)
        y_hits = np.array([item.total_hits for item in items], dtype=float)

        fig, axes = plt.subplots(3, 1, figsize=(8, 14), sharex=True)
        axes[0].plot(x, y_sat, marker="o", linewidth=2, color="#b23a48")
        axes[0].set_ylabel("Saturation [%]", fontsize=16)
        axes[0].set_title(f"Threshold dependence: ASU {asu_label}", fontsize=20)
        axes[0].grid(True, alpha=0.25)

        axes[1].plot(x, y_alive, marker="o", linewidth=2, color="#5b8e7d")
        axes[1].set_ylabel("Alive fraction [%]", fontsize=16)
        axes[1].grid(True, alpha=0.25)

        axes[2].plot(x, y_hits, marker="o", linewidth=2, color="#497c88")
        axes[2].set_xlabel("Threshold DAC", fontsize=16)
        axes[2].set_ylabel("Total hits", fontsize=16)
        axes[2].grid(True, alpha=0.25)

        for ax in axes:
            ax.tick_params(axis="both", labelsize=12)

        fig.tight_layout()
        fig.savefig(output_dir / f"asu_{asu_label}_threshold_dependence.pdf")
        plt.close(fig)


def serialize_metrics(metrics: dict[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in metrics.items():
        if isinstance(value, np.ndarray):
            serialized[key] = value.tolist()
        elif isinstance(value, (np.floating, np.integer)):
            serialized[key] = value.item()
        else:
            serialized[key] = value
    return serialized


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
