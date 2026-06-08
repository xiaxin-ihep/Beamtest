from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import struct
import subprocess

import numpy as np


RAW_SEGMENT_RE = re.compile(r"^(?P<stem>.+)\.bin(?:_(?P<index>\d{4}))?$")
ASCII_SEGMENT_RE = re.compile(r"^(?P<stem>.+)\.dat$")
SOURCE_FRAME_MAGIC = b"\xee\xee\xee\xee"

SLBDEPTH = 15
NB_OF_SKIROCS_PER_ASU = 16
NB_OF_SCAS_IN_SKIROC = 15
NB_OF_CHANNELS_IN_SKIROC = 64

SOURCE_FRAME_HEADER = struct.Struct("<iiBbbbBBIIIIIIfff")
SOURCE_SUBEVENT_HEADER = struct.Struct("<IHBI")
SOURCE_CHANNEL_RECORD = struct.Struct("<BHBBHBB")
SOURCE_FRAME_TRAILER_BYTES = 4


@dataclass
class RawSegment:
    source: Path
    index: int


@dataclass
class SourceSubevent:
    event_index: int
    bcid: int
    sca: int
    nhits: int
    adc_low: np.ndarray
    adc_high: np.ndarray
    autogainbit_low: np.ndarray
    autogainbit_high: np.ndarray
    hitbit_low: np.ndarray
    hitbit_high: np.ndarray


@dataclass
class SourceFrame:
    source_index: int
    frame_index_in_file: int
    header_offset: int
    event_number: int
    n_sca: int
    chip_id: int
    core_daughter_index: int
    slab_index: int
    slab_add: int
    asu_index: int
    skiroc_index: int
    transmit_id: int
    cycle_id: int
    start_acq_timestamp: int
    raw_tsd: int
    raw_avdd0: int
    raw_avdd1: int
    tsd_value: float
    avdd0: float
    avdd1: float
    subevents: list[SourceSubevent]


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
    if segments:
        return segments

    ascii_segments = sorted(path for path in input_dir.iterdir() if path.is_file() and ASCII_SEGMENT_RE.match(path.name))
    if ascii_segments:
        return [RawSegment(source=path, index=index) for index, path in enumerate(ascii_segments)]
    raise FileNotFoundError(f"No source .bin/.bin_XXXX or .dat files found under {input_dir}")


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
        suffix = segment.source.suffix.replace(".", "")
        target = staging_dir / f"{run_name}_raw.{suffix}_{segment.index:04d}"
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


def _is_ascii_source(path: Path) -> bool:
    return path.suffix.lower() == ".dat"


def _candidate_source_headers(data: bytes) -> list[int]:
    starts: list[int] = []
    search_from = 0
    while True:
        index = data.find(SOURCE_FRAME_MAGIC, search_from)
        if index == -1:
            break
        if index + 12 <= len(data):
            n_sca = int.from_bytes(data[index + 8 : index + 12], "little", signed=True)
            if 0 < n_sca <= NB_OF_SCAS_IN_SKIROC:
                starts.append(index)
        search_from = index + 4
    return starts


def _parse_source_channel_block(payload: bytes, offset: int) -> tuple[np.ndarray, ...]:
    adc_low = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
    adc_high = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
    autogainbit_low = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
    autogainbit_high = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
    hitbit_low = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
    hitbit_high = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)

    for _ in range(NB_OF_CHANNELS_IN_SKIROC):
        channel_id, low_value, low_hit, low_gain, high_value, high_hit, high_gain = SOURCE_CHANNEL_RECORD.unpack_from(payload, offset)
        offset += SOURCE_CHANNEL_RECORD.size
        if channel_id >= NB_OF_CHANNELS_IN_SKIROC:
            raise ValueError(f"Invalid channel id {channel_id}")
        adc_low[channel_id] = low_value
        adc_high[channel_id] = high_value
        autogainbit_low[channel_id] = low_gain
        autogainbit_high[channel_id] = high_gain
        hitbit_low[channel_id] = low_hit
        hitbit_high[channel_id] = high_hit

    return adc_low, adc_high, autogainbit_low, autogainbit_high, hitbit_low, hitbit_high


def _parse_binary_source_file(input_file: Path, source_index: int) -> tuple[str, list[SourceFrame], dict[str, object]]:
    data = input_file.read_bytes()
    starts = _candidate_source_headers(data)
    if not starts:
        raise ValueError(f"No source-frame headers found in {input_file}")

    header_prefix = data[: starts[0]].decode(errors="ignore")
    frames: list[SourceFrame] = []
    for frame_index, start in enumerate(starts):
        header = SOURCE_FRAME_HEADER.unpack_from(data, start + 4)
        event_number, n_sca, chip_id, core_idx, slab_idx, slab_add, asu_index, skiroc_index, transmit_id, cycle_id, start_ts, raw_tsd, raw_avdd0, raw_avdd1, tsd_value, avdd0, avdd1 = header
        offset = start + 4 + SOURCE_FRAME_HEADER.size
        subevents: list[SourceSubevent] = []
        for _ in range(n_sca):
            single_event_number, bcid, sca, nhits = SOURCE_SUBEVENT_HEADER.unpack_from(data, offset)
            offset += SOURCE_SUBEVENT_HEADER.size
            adc_low, adc_high, autogainbit_low, autogainbit_high, hitbit_low, hitbit_high = _parse_source_channel_block(data, offset)
            offset += NB_OF_CHANNELS_IN_SKIROC * SOURCE_CHANNEL_RECORD.size
            subevents.append(
                SourceSubevent(
                    event_index=single_event_number,
                    bcid=bcid,
                    sca=sca,
                    nhits=nhits,
                    adc_low=adc_low,
                    adc_high=adc_high,
                    autogainbit_low=autogainbit_low,
                    autogainbit_high=autogainbit_high,
                    hitbit_low=hitbit_low,
                    hitbit_high=hitbit_high,
                )
            )

        offset += SOURCE_FRAME_TRAILER_BYTES
        frames.append(
            SourceFrame(
                source_index=source_index,
                frame_index_in_file=frame_index,
                header_offset=start,
                event_number=event_number,
                n_sca=n_sca,
                chip_id=chip_id,
                core_daughter_index=core_idx,
                slab_index=slab_idx,
                slab_add=slab_add,
                asu_index=asu_index,
                skiroc_index=skiroc_index,
                transmit_id=transmit_id,
                cycle_id=cycle_id,
                start_acq_timestamp=start_ts,
                raw_tsd=raw_tsd,
                raw_avdd0=raw_avdd0,
                raw_avdd1=raw_avdd1,
                tsd_value=tsd_value,
                avdd0=avdd0,
                avdd1=avdd1,
                subevents=subevents,
            )
        )

    metadata = {
        "input_file": str(input_file),
        "format": "binary-decoded-frames",
        "header_prefix_bytes": starts[0],
        "n_candidate_frames": len(frames),
        "first_event": int(frames[0].event_number),
        "last_event": int(frames[-1].event_number),
    }
    return header_prefix, frames, metadata


def _parse_ascii_channel(line: str) -> tuple[int, int, int, int, int, int, int]:
    match = re.match(r"Ch\s+(\d+)\s+LG\s+(\d+)\s+(\d+)\s+(\d+)\s+HG\s+(\d+)\s+(\d+)\s+(\d+)", line)
    if not match:
        raise ValueError(f"Could not parse channel line: {line}")
    return tuple(int(group) for group in match.groups())


def _parse_ascii_source_file(input_file: Path, source_index: int) -> tuple[str, list[SourceFrame], dict[str, object]]:
    frames: list[SourceFrame] = []
    header_lines: list[str] = []
    frame_header_re = re.compile(
        r"#(\d+)\s+Size\s+(\d+)\s+ChipID\s+(-?\d+)\s+coreIdx\s+(-?\d+)\s+slabIdx\s+(-?\d+)\s+slabAdd\s+(-?\d+)\s+Asu\s+(\d+)\s+SkirocIndex\s+(\d+)\s+transmitID\s+(\d+)\s+cycleID\s+(\d+)\s+StartTime\s+(\d+)\s+rawTSD\s+(\d+)\s+rawAVDD0\s+(\d+)\s+rawAVDD1\s+(\d+)\s+tsdValue\s+([0-9.]+)\s+avDD0\s+([0-9.]+)\s+aVDD1\s+([0-9.]+)"
    )
    subevent_header_re = re.compile(r"##(\d+)\s+BCID\s+(\d+)\s+SCA\s+(\d+)\s+#Hits\s+(\d+)")

    with input_file.open("r", errors="ignore") as handle:
        while True:
            line = handle.readline()
            if not line:
                break
            stripped = line.strip()
            if not stripped.startswith("#"):
                if len(header_lines) < 10:
                    header_lines.append(line.rstrip("\n"))
                continue
            if stripped.startswith("##"):
                raise ValueError(f"Unexpected subevent header before frame header in {input_file}: {stripped}")

            frame_match = frame_header_re.match(stripped)
            if not frame_match:
                raise ValueError(f"Could not parse frame header in {input_file}: {stripped}")

            event_number, n_sca, chip_id, core_idx, slab_idx, slab_add, asu_index, skiroc_index, transmit_id, cycle_id, start_ts, raw_tsd, raw_avdd0, raw_avdd1, tsd_value, avdd0, avdd1 = frame_match.groups()

            subevents: list[SourceSubevent] = []
            for _ in range(int(n_sca)):
                sub_line = handle.readline()
                if not sub_line:
                    raise ValueError(f"Unexpected EOF while reading subevent headers in {input_file}")
                sub_match = subevent_header_re.match(sub_line.strip())
                if not sub_match:
                    raise ValueError(f"Could not parse subevent header in {input_file}: {sub_line.strip()}")
                single_event_number, bcid, sca, nhits = (int(value) for value in sub_match.groups())

                adc_low = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
                adc_high = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
                autogainbit_low = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
                autogainbit_high = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
                hitbit_low = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
                hitbit_high = np.zeros(NB_OF_CHANNELS_IN_SKIROC, dtype=np.int32)
                for _channel in range(NB_OF_CHANNELS_IN_SKIROC):
                    channel_line = handle.readline()
                    if not channel_line:
                        raise ValueError(f"Unexpected EOF while reading channel payload in {input_file}")
                    channel_id, low_value, low_hit, low_gain, high_value, high_hit, high_gain = _parse_ascii_channel(channel_line.strip())
                    adc_low[channel_id] = low_value
                    adc_high[channel_id] = high_value
                    autogainbit_low[channel_id] = low_gain
                    autogainbit_high[channel_id] = high_gain
                    hitbit_low[channel_id] = low_hit
                    hitbit_high[channel_id] = high_hit

                subevents.append(
                    SourceSubevent(
                        event_index=single_event_number,
                        bcid=bcid,
                        sca=sca,
                        nhits=nhits,
                        adc_low=adc_low,
                        adc_high=adc_high,
                        autogainbit_low=autogainbit_low,
                        autogainbit_high=autogainbit_high,
                        hitbit_low=hitbit_low,
                        hitbit_high=hitbit_high,
                    )
                )

            frames.append(
                SourceFrame(
                    source_index=source_index,
                    frame_index_in_file=len(frames),
                    header_offset=-1,
                    event_number=int(event_number),
                    n_sca=int(n_sca),
                    chip_id=int(chip_id),
                    core_daughter_index=int(core_idx),
                    slab_index=int(slab_idx),
                    slab_add=int(slab_add),
                    asu_index=int(asu_index),
                    skiroc_index=int(skiroc_index),
                    transmit_id=int(transmit_id),
                    cycle_id=int(cycle_id),
                    start_acq_timestamp=int(start_ts),
                    raw_tsd=int(raw_tsd),
                    raw_avdd0=int(raw_avdd0),
                    raw_avdd1=int(raw_avdd1),
                    tsd_value=float(tsd_value),
                    avdd0=float(avdd0),
                    avdd1=float(avdd1),
                    subevents=subevents,
                )
            )

    metadata = {
        "input_file": str(input_file),
        "format": "ascii-decoded-frames",
        "header_prefix_bytes": 0,
        "n_candidate_frames": len(frames),
        "first_event": int(frames[0].event_number),
        "last_event": int(frames[-1].event_number),
    }
    return "\n".join(header_lines[:10]), frames, metadata


def _parse_source_file(segment: RawSegment) -> tuple[str, list[SourceFrame], dict[str, object]]:
    if _is_ascii_source(segment.source):
        return _parse_ascii_source_file(segment.source, segment.index)
    return _parse_binary_source_file(segment.source, segment.index)


def _chunk_frames_into_acquisitions(frames: list[SourceFrame]) -> tuple[list[list[SourceFrame]], list[dict[str, object]]]:
    acquisitions: list[list[SourceFrame]] = []
    dropped: list[dict[str, object]] = []
    current: list[SourceFrame] = []
    seen_chips: set[int] = set()

    for frame in frames:
        if current and frame.chip_id in seen_chips:
            if len(current) == NB_OF_SKIROCS_PER_ASU:
                acquisitions.append(current)
            else:
                dropped.append(
                    {
                        "reason": "duplicate-chip-before-acquisition-complete",
                        "frame_indices": [item.frame_index_in_file for item in current],
                        "chip_ids": [item.chip_id for item in current],
                    }
                )
            current = []
            seen_chips = set()

        current.append(frame)
        seen_chips.add(frame.chip_id)
        if len(current) == NB_OF_SKIROCS_PER_ASU:
            acquisitions.append(current)
            current = []
            seen_chips = set()

    if current:
        dropped.append(
            {
                "reason": "incomplete-final-acquisition",
                "frame_indices": [item.frame_index_in_file for item in current],
                "chip_ids": [item.chip_id for item in current],
            }
        )

    return acquisitions, dropped


def _build_tree_payload_from_frames(frames: list[SourceFrame]) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    acquisitions, dropped = _chunk_frames_into_acquisitions(frames)
    n_entries = len(acquisitions)

    slot = np.full((n_entries, SLBDEPTH), -1, dtype=np.int32)
    slboard_id = np.full((n_entries, SLBDEPTH), -1, dtype=np.int32)
    chipid = np.full((n_entries, SLBDEPTH, NB_OF_SKIROCS_PER_ASU), -999, dtype=np.int32)
    ncolumns = np.zeros((n_entries, SLBDEPTH, NB_OF_SKIROCS_PER_ASU), dtype=np.int32)
    start_acq = np.full((n_entries, SLBDEPTH), -1.0, dtype=np.float32)
    raw_tsd = np.full((n_entries, SLBDEPTH), -1, dtype=np.int32)
    tsd = np.full((n_entries, SLBDEPTH), -1.0, dtype=np.float32)
    raw_avdd0 = np.full((n_entries, SLBDEPTH), -1, dtype=np.int32)
    raw_avdd1 = np.full((n_entries, SLBDEPTH), -1, dtype=np.int32)
    avdd0 = np.full((n_entries, SLBDEPTH), -1.0, dtype=np.float32)
    avdd1 = np.full((n_entries, SLBDEPTH), -1.0, dtype=np.float32)
    bcid = np.full((n_entries, SLBDEPTH, NB_OF_SKIROCS_PER_ASU, NB_OF_SCAS_IN_SKIROC), -999, dtype=np.int32)
    corrected_bcid = np.full_like(bcid, -999)
    badbcid = np.full_like(bcid, -999)
    nhits = np.full_like(bcid, -999)
    adc_low = np.full((n_entries, SLBDEPTH, NB_OF_SKIROCS_PER_ASU, NB_OF_SCAS_IN_SKIROC, NB_OF_CHANNELS_IN_SKIROC), -999, dtype=np.int32)
    adc_high = np.full_like(adc_low, -999)
    autogainbit_low = np.full_like(adc_low, -999)
    autogainbit_high = np.full_like(adc_low, -999)
    hitbit_low = np.full_like(adc_low, -999)
    hitbit_high = np.full_like(adc_low, -999)

    chip_permutations: list[list[int]] = []
    asu_indices: set[int] = set()
    cycle_ids: set[int] = set()

    for entry_index, acquisition in enumerate(acquisitions):
        chip_permutations.append([frame.chip_id for frame in acquisition])
        for frame in acquisition:
            layer_index = 0
            chip_index = frame.chip_id if 0 <= frame.chip_id < NB_OF_SKIROCS_PER_ASU else frame.skiroc_index
            if chip_index < 0 or chip_index >= NB_OF_SKIROCS_PER_ASU:
                continue

            asu_indices.add(frame.asu_index)
            cycle_ids.add(frame.cycle_id)
            slot[entry_index, layer_index] = frame.asu_index
            slboard_id[entry_index, layer_index] = frame.asu_index
            chipid[entry_index, layer_index, chip_index] = frame.chip_id
            ncolumns[entry_index, layer_index, chip_index] = frame.n_sca
            start_acq[entry_index, layer_index] = float(frame.start_acq_timestamp)
            raw_tsd[entry_index, layer_index] = frame.raw_tsd
            tsd[entry_index, layer_index] = float(frame.tsd_value)
            raw_avdd0[entry_index, layer_index] = frame.raw_avdd0
            raw_avdd1[entry_index, layer_index] = frame.raw_avdd1
            avdd0[entry_index, layer_index] = float(frame.avdd0)
            avdd1[entry_index, layer_index] = float(frame.avdd1)

            for subevent in frame.subevents:
                sca_slot = subevent.sca
                if sca_slot < 0 or sca_slot >= NB_OF_SCAS_IN_SKIROC:
                    continue
                bcid[entry_index, layer_index, chip_index, sca_slot] = subevent.bcid
                corrected_bcid[entry_index, layer_index, chip_index, sca_slot] = subevent.bcid
                badbcid[entry_index, layer_index, chip_index, sca_slot] = 0
                nhits[entry_index, layer_index, chip_index, sca_slot] = subevent.nhits
                adc_low[entry_index, layer_index, chip_index, sca_slot, :] = subevent.adc_low
                adc_high[entry_index, layer_index, chip_index, sca_slot, :] = subevent.adc_high
                autogainbit_low[entry_index, layer_index, chip_index, sca_slot, :] = subevent.autogainbit_low
                autogainbit_high[entry_index, layer_index, chip_index, sca_slot, :] = subevent.autogainbit_high
                hitbit_low[entry_index, layer_index, chip_index, sca_slot, :] = subevent.hitbit_low
                hitbit_high[entry_index, layer_index, chip_index, sca_slot, :] = subevent.hitbit_high

    payload = {
        "acqNumber": np.arange(n_entries, dtype=np.int32),
        "n_slboards": np.ones(n_entries, dtype=np.int32),
        "slot": slot,
        "slboard_id": slboard_id,
        "chipid": chipid,
        "nColumns": ncolumns,
        "startACQ": start_acq,
        "rawTSD": raw_tsd,
        "TSD": tsd,
        "rawAVDD0": raw_avdd0,
        "rawAVDD1": raw_avdd1,
        "AVDD0": avdd0,
        "AVDD1": avdd1,
        "bcid": bcid,
        "corrected_bcid": corrected_bcid,
        "badbcid": badbcid,
        "nhits": nhits,
        "adc_low": adc_low,
        "adc_high": adc_high,
        "autogainbit_low": autogainbit_low,
        "autogainbit_high": autogainbit_high,
        "hitbit_low": hitbit_low,
        "hitbit_high": hitbit_high,
    }
    metadata = {
        "n_total_frames": len(frames),
        "n_acquisitions": n_entries,
        "n_dropped_frame_groups": len(dropped),
        "dropped_frame_groups": dropped[:20],
        "chip_order_first_acquisition": chip_permutations[0] if chip_permutations else [],
        "asu_indices_seen": sorted(asu_indices),
        "cycle_ids_seen_sample": sorted(cycle_ids)[:20],
    }
    return payload, metadata


def convert_source_binary_to_root(
    input_dir: str | Path,
    output_root: str | Path,
    run_name: str,
    store_full_bytes: bool = False,
) -> dict[str, object]:
    del store_full_bytes
    try:
        import uproot
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("convert_source_binary_to_root requires uproot") from exc

    input_dir = Path(input_dir)
    output_root = Path(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)

    segments = detect_raw_segments(input_dir)
    header_texts: list[str] = []
    all_frames: list[SourceFrame] = []
    per_file: list[dict[str, object]] = []
    global_index = 0

    for segment in segments:
        header_text, frames, metadata = _parse_source_file(segment)
        header_texts.append(header_text)
        for frame in frames:
            frame.frame_index_in_file = global_index
            frame.source_index = segment.index
            global_index += 1
            all_frames.append(frame)
        metadata["segment_index"] = segment.index
        metadata["source_name"] = segment.source.name
        per_file.append(metadata)

    tree_payload, tree_metadata = _build_tree_payload_from_frames(all_frames)

    with uproot.recreate(output_root) as handle:
        handle["siwecaldecoded"] = tree_payload

    summary = {
        "run_name": run_name,
        "input_dir": str(input_dir),
        "output_root": str(output_root),
        "n_segments": len(segments),
        "segment_types": sorted({metadata["format"] for metadata in per_file}),
        "per_file": per_file,
        "header_prefix_preview": header_texts[0][:300] if header_texts else "",
        **tree_metadata,
    }
    summary_path = output_root.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    return summary
