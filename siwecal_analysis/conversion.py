from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import json

import numpy as np


RAW_SEGMENT_RE = re.compile(r"^(?P<stem>.+)\.bin(?:_(?P<index>\d{4}))?$")
SOURCE_FRAME_MAGIC = b"\xee\xee\xee\xee"


@dataclass
class RawSegment:
    source: Path
    index: int


@dataclass
class SourceFrame:
    source_index: int
    frame_index_in_file: int
    header_offset: int
    event_number: int
    n_sca: int
    marker_a: int
    marker_b: int
    marker_c: int
    payload_nbytes: int
    preview_bytes: bytes


def detect_raw_segments(input_dir: str | Path) -> list[RawSegment]:
    input_dir = Path(input_dir)
    segments: list[RawSegment] = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        match = RAW_SEGMENT_RE.match(path.name)
        if not match:
            continue
        index = int(match.group("index") or "0000")
        segments.append(RawSegment(source=path, index=index))
    if not segments:
        raise FileNotFoundError(f"No .bin or .bin_XXXX files found under {input_dir}")
    return segments


def stage_raw_segments(
    input_dir: str | Path,
    staging_dir: str | Path,
    run_name: str,
    copy_files: bool = False,
) -> list[Path]:
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_paths: list[Path] = []
    for segment in detect_raw_segments(input_dir):
        target = staging_dir / f"{run_name}_raw.bin_{segment.index:04d}"
        if target.exists() or target.is_symlink():
            target.unlink()
        if copy_files:
            target.write_bytes(segment.source.read_bytes())
        else:
            os.symlink(segment.source, target)
        staged_paths.append(target)
    return staged_paths


def run_root_conversion(
    staged_raw_dir: str | Path,
    run_name: str,
    output_dir: str | Path,
    macro_path: str | Path,
) -> None:
    staged_raw_dir = Path(staged_raw_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_root in output_dir.glob("converted_*.root"):
        old_root.unlink()

    macro_path = Path(macro_path).resolve()
    command = [
        "root",
        "-l",
        "-b",
        "-q",
        f'{macro_path}("{staged_raw_dir}/",false,"{run_name}","{output_dir}",0)',
    ]
    subprocess.run(command, check=True)


def list_root_files(run_dir: str | Path) -> list[Path]:
    run_dir = Path(run_dir)
    files = sorted(run_dir.glob("*.root"))
    if not files:
        raise FileNotFoundError(f"No ROOT files found under {run_dir}")
    return files


def convert_root_to_decoupechannel(
    run_dir: str | Path,
    layers: list[int] | None = None,
    tree_name: str = "siwecaldecoded",
) -> dict[int, Path]:
    try:
        import uproot
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("convert_root_to_decoupechannel requires 'uproot'") from exc

    run_dir = Path(run_dir)
    root_files = list_root_files(run_dir)

    with uproot.open(root_files[0]) as handle:
        tree = handle[tree_name]
        branch_names = set(tree.keys())

    selected_branches = ["adc_high", "hitbit_high", "badbcid"]
    if "adc_trig" in branch_names:
        selected_branches.append("adc_trig")

    layer_paths: dict[int, Path] = {}
    for root_file in root_files:
        with uproot.open(root_file) as handle:
            tree = handle[tree_name]
            arrays = tree.arrays(selected_branches, library="np")

        adc_high = np.clip(arrays["adc_high"], 0, None).astype(np.uint16)
        hitbit_high = np.clip(arrays["hitbit_high"], 0, None).astype(np.bool_)
        adc_trig = np.clip(arrays["adc_trig"], 0, None).astype(np.uint16) if "adc_trig" in arrays else None
        badbcid = np.clip(arrays["badbcid"], 0, None).astype(np.bool_)

        available_layers = list(range(adc_high.shape[1]))
        target_layers = available_layers if layers is None else layers

        for layer in target_layers:
            layer_dir = run_dir / "decoupechannel" / f"layer{layer}"
            layer_dir.mkdir(parents=True, exist_ok=True)
            layer_paths[layer] = layer_dir

            layer_adc = adc_high[:, layer, :, :, :]
            layer_hit = hitbit_high[:, layer, :, :, :]
            layer_badbcid = badbcid[:, layer, :, :]
            layer_trig = adc_trig[:, layer, :, :, :] if adc_trig is not None else None

            for channel in range(layer_adc.shape[3]):
                adc_path = layer_dir / f"adc_high_array{channel}.npy"
                hit_path = layer_dir / f"hitbit_high_array{channel}.npy"
                trig_path = layer_dir / f"adc_trig_array{channel}.npy"

                adc_payload = layer_adc[:, :, :, channel]
                hit_payload = layer_hit[:, :, :, channel]
                if adc_path.exists():
                    adc_payload = np.concatenate((np.load(adc_path), adc_payload), axis=0)
                if hit_path.exists():
                    hit_payload = np.concatenate((np.load(hit_path), hit_payload), axis=0)
                np.save(adc_path, adc_payload)
                np.save(hit_path, hit_payload)

                if layer_trig is not None:
                    trig_payload = layer_trig[:, :, :, channel]
                    if trig_path.exists():
                        trig_payload = np.concatenate((np.load(trig_path), trig_payload), axis=0)
                    np.save(trig_path, trig_payload)

            badbcid_path = layer_dir / "badbcid_array.npy"
            if badbcid_path.exists():
                layer_badbcid = np.concatenate((np.load(badbcid_path), layer_badbcid), axis=0)
            np.save(badbcid_path, layer_badbcid)

    return layer_paths


def _candidate_source_headers(data: bytes) -> list[int]:
    starts: list[int] = []
    search_from = 0
    while True:
        index = data.find(SOURCE_FRAME_MAGIC, search_from)
        if index == -1:
            break
        next_words = [int.from_bytes(data[index + 4 + 4 * i : index + 8 + 4 * i], "little", signed=True) for i in range(5)]
        if len(next_words) == 5 and next_words[1] == 15:
            starts.append(index)
        search_from = index + 4
    return starts


def extract_source_frames(input_file: str | Path) -> tuple[str, list[SourceFrame], dict[str, object]]:
    input_file = Path(input_file)
    data = input_file.read_bytes()
    starts = _candidate_source_headers(data)
    if not starts:
        raise ValueError(f"No source-frame headers found in {input_file}")

    header_prefix = data[: starts[0]].decode(errors="ignore")
    frames: list[SourceFrame] = []
    event_numbers: list[int] = []
    for frame_index, start in enumerate(starts):
        end = starts[frame_index + 1] if frame_index + 1 < len(starts) else len(data)
        chunk = data[start:end]
        event_number = int.from_bytes(chunk[4:8], "little", signed=False)
        n_sca = int.from_bytes(chunk[8:12], "little", signed=True)
        marker_a = int.from_bytes(chunk[12:16], "little", signed=True)
        marker_b = int.from_bytes(chunk[16:20], "little", signed=True)
        marker_c = int.from_bytes(chunk[20:24], "little", signed=True)
        frames.append(
            SourceFrame(
                source_index=0,
                frame_index_in_file=frame_index,
                header_offset=start,
                event_number=event_number,
                n_sca=n_sca,
                marker_a=marker_a,
                marker_b=marker_b,
                marker_c=marker_c,
                payload_nbytes=len(chunk),
                preview_bytes=chunk[:128],
            )
        )
        event_numbers.append(event_number)

    gaps: list[dict[str, int]] = []
    for previous, current in zip(event_numbers, event_numbers[1:]):
        if current != previous + 1:
            gaps.append({"previous": previous, "current": current, "delta": current - previous})

    metadata = {
        "input_file": str(input_file),
        "header_prefix_bytes": starts[0],
        "n_candidate_frames": len(frames),
        "first_event": event_numbers[0],
        "last_event": event_numbers[-1],
        "n_event_gaps": len(gaps),
        "first_gaps": gaps[:50],
    }
    return header_prefix, frames, metadata


def convert_source_binary_to_root(
    input_dir: str | Path,
    output_root: str | Path,
    run_name: str,
    store_full_bytes: bool = False,
) -> dict[str, object]:
    try:
        import awkward as ak
        import uproot
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("convert_source_binary_to_root requires awkward and uproot") from exc

    input_dir = Path(input_dir)
    output_root = Path(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)

    segments = detect_raw_segments(input_dir)
    header_texts: list[str] = []
    all_frames: list[SourceFrame] = []
    per_file: list[dict[str, object]] = []
    global_index = 0
    for segment in segments:
        header_text, frames, metadata = extract_source_frames(segment.source)
        header_texts.append(header_text)
        for local_index, frame in enumerate(frames):
            frame.source_index = segment.index
            frame.frame_index_in_file = global_index
            global_index += 1
            all_frames.append(
                SourceFrame(
                    source_index=segment.index,
                    frame_index_in_file=frame.frame_index_in_file,
                    header_offset=frame.header_offset,
                    event_number=frame.event_number,
                    n_sca=frame.n_sca,
                    marker_a=frame.marker_a,
                    marker_b=frame.marker_b,
                    marker_c=frame.marker_c,
                    payload_nbytes=frame.payload_nbytes,
                    preview_bytes=frame.preview_bytes,
                )
            )
        metadata["segment_index"] = segment.index
        per_file.append(metadata)

    preview_matrix = np.zeros((len(all_frames), 128), dtype=np.uint8)
    for row, frame in enumerate(all_frames):
        preview = np.frombuffer(frame.preview_bytes, dtype=np.uint8)
        preview_matrix[row, : preview.size] = preview

    tree_payload = {
        "source_index": np.array([frame.source_index for frame in all_frames], dtype=np.int32),
        "frame_index": np.array([frame.frame_index_in_file for frame in all_frames], dtype=np.int32),
        "header_offset": np.array([frame.header_offset for frame in all_frames], dtype=np.int64),
        "event_number": np.array([frame.event_number for frame in all_frames], dtype=np.int32),
        "n_sca": np.array([frame.n_sca for frame in all_frames], dtype=np.int32),
        "marker_a": np.array([frame.marker_a for frame in all_frames], dtype=np.int32),
        "marker_b": np.array([frame.marker_b for frame in all_frames], dtype=np.int32),
        "marker_c": np.array([frame.marker_c for frame in all_frames], dtype=np.int32),
        "frame_nbytes": np.array([frame.payload_nbytes for frame in all_frames], dtype=np.int32),
        "frame_preview_128": preview_matrix,
    }

    if store_full_bytes:
        payloads = ak.Array([np.frombuffer(frame.preview_bytes, dtype=np.uint8) for frame in all_frames])
        tree_payload["frame_bytes"] = payloads

    with uproot.recreate(output_root) as handle:
        handle["source_raw"] = tree_payload

    summary = {
        "run_name": run_name,
        "input_dir": str(input_dir),
        "output_root": str(output_root),
        "n_segments": len(segments),
        "n_total_frames": len(all_frames),
        "per_file": per_file,
        "header_prefix_preview": header_texts[0][:300] if header_texts else "",
    }
    summary_path = output_root.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary
