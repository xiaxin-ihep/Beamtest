# ECAL Test Analysis

This directory contains a cleaned analysis framework for two workflows:

- `beam test`
- `source test`

The code is organized so that both workflows share common utilities while keeping their entry points and usage separate.

## Purpose

The framework provides:

- reusable file I/O helpers
- mapping utilities
- plotting helpers
- beam-test analysis scripts
- source-test analysis scripts
- conversion helpers for ROOT, `decoupechannel`, and source raw files

## Directory Structure

```text
ECAL_Test_Analysis/
├── README.md
├── beam_test/
├── output/
├── run_source_pipeline.sh
├── source_test/
├── scripts/
│   ├── analyze_hit_map.py
│   ├── analyze_hits_histogram.py
│   ├── analyze_hold_scan.py
│   ├── analyze_pedestal.py
│   ├── analyze_signal_map.py
│   ├── analyze_source_run.py
│   ├── convert_binary_to_root.py
│   ├── convert_root_to_npy.py
│   ├── convert_source_binary_to_root.py
│   └── run_source_pipeline.py
└── siwecal_analysis/
    ├── analysis.py
    ├── config.py
    ├── conversion.py
    ├── io.py
    ├── mapping.py
    ├── plotting.py
    └── source_analysis.py
```

## Environment

Use the `r6.28` conda environment:

```bash
conda activate r6.28
```

Required packages:

```bash
python -c "import numpy, scipy, matplotlib, uproot, ROOT"
```

## Beam Test Workflow

Beam-test analysis is intended for:

- pedestal maps
- noise checks
- hit maps
- signal / amplitude maps
- S/N maps
- hold-value scans

Main scripts:

- `scripts/analyze_pedestal.py`
- `scripts/analyze_hit_map.py`
- `scripts/analyze_signal_map.py`
- `scripts/analyze_hold_scan.py`

Typical input:

- converted ROOT files
- `decoupechannel/layerX/*.npy`

Typical output directories:

- `output/pedestal/`
- `output/hitmap/`
- `output/signal/`
- `output/hold_scan/`

See:

- [beam_test/README.md](/Users/xiaxin/Desktop/work/TB_Desy/TB2025-03/SiWECAL-TB-analysis/script_victor_cp/local_analysis/ECAL_Test_Analysis/beam_test/README.md:1)

## Source Test Workflow

Source-test analysis provides tools for:

- occupancy visualization
- source-driven activity maps
- saturation summaries
- frame-level inspection of source raw files

Main scripts and wrappers:

- `scripts/analyze_hits_histogram.py`
- `source_test/run_hits_histogram_fallback.sh`
- `scripts/convert_source_binary_to_root.py`
- `source_test/run_source_raw_converter.sh`
- `run_source_pipeline.sh`

Typical input:

```text
input/<run_name>/
├── Run_Settings.txt
├── hitsHistogram.txt
├── logfile.txt
├── <run_name>.bin
└── <run_name>.bin_0001
```

Typical output directories:

- `output/hitsHistogram/`
- `output/source_raw/`
- `output/pipeline/`

See:

- [source_test/README.md](/Users/xiaxin/Desktop/work/TB_Desy/TB2025-03/SiWECAL-TB-analysis/script_victor_cp/local_analysis/ECAL_Test_Analysis/source_test/README.md:1)

## Beam Test Usage

### Pedestal

```bash
python scripts/analyze_pedestal.py \
  --run 587 \
  --layer 1 \
  --memory 0
```

### Hit Map

```bash
python scripts/analyze_hit_map.py \
  --run 587 \
  --layer 1 \
  --memory -1
```

### Signal / SNR

```bash
python scripts/analyze_signal_map.py \
  --run 587 \
  --layer 1 \
  --memory 0 \
  --pedestal-file output/pedestal/Run_ILC_20250304_masking_it3_2_eudaq_run_090587_layer1_pedestal.npz
```

### Hold Scan

```bash
python scripts/analyze_hold_scan.py \
  --runs 586 589 590 591 592 593 595 \
  --hold-values 50 70 90 110 130 150 170 \
  --layer 1 \
  --chip 12 \
  --memory 0 \
  --channel 13 \
  --use-hitbit 1
```

## Source Test Usage

### hitsHistogram Analysis

```bash
./source_test/run_hits_histogram_fallback.sh \
  input/source_asu_2026_004_th250_run_000008 \
  0
```

Equivalent direct command:

```bash
python scripts/analyze_hits_histogram.py \
  --histogram-file input/source_asu_2026_004_th250_run_000008/hitsHistogram.txt \
  --run-name source_asu_2026_004_th250_run_000008 \
  --layer 0 \
  --output-dir output/hitsHistogram/source_asu_2026_004_th250_run_000008
```

### Source Raw ROOT Conversion

```bash
./source_test/run_source_raw_converter.sh \
  input/source_asu_2026_004_th250_run_000008
```

### Full Source Wrapper

```bash
./run_source_pipeline.sh \
  input/source_asu_2026_004_th250_run_000008 \
  0
```

## Source Plot Settings

Source-test plots are configured with:

- PDF output
- title format `Source_test_2026_00x_thxxx`
- x-axis label font size `20`
- y-axis label font size `20`

## Output Summary

### Beam Test

- mapped analysis arrays
- channel-level arrays
- pedestal files
- hit / signal / SNR maps
- hold scan curves

### Source Test

- `hitsHistogram` map PDF
- `hitsHistogram` summary JSON
- source raw ROOT file
- source raw summary JSON

## Notes

- For beam-test `decoupechannel` data, a single channel file has shape `(n_windows, 16, 15)`.
- `--memory -1` means “merge all memory cells”.
- The `source_raw` ROOT converter is available as a source-test intermediate tool.
