# Source Test

This directory documents the workflow for `ecal alone` source-test data.

## Purpose

The source-test workflow is intended for:

- occupancy checks
- hot-region visualization
- channel activity summaries
- source-run quick validation

## Available Tools

### hitsHistogram Analysis

Use the DAQ `hitsHistogram.txt` input:

```bash
./run_hits_histogram_fallback.sh \
  ../input/source_asu_2026_004_th250_run_000008 \
  0
```

This wrapper runs:

```bash
python ../scripts/analyze_hits_histogram.py ...
```

### Source Raw ROOT Conversion

Use this command to write a ROOT-level intermediate file for source raw frames:

```bash
./run_source_raw_converter.sh \
  ../input/source_asu_2026_004_th250_run_000008
```

This creates a `source_raw` ROOT tree.

### Full Source Pipeline

Use the full wrapper with:

```bash
../run_source_pipeline.sh \
  ../input/source_asu_2026_004_th250_run_000008 \
  0
```

This wrapper calls:

- binary staging
- binary to ROOT
- ROOT to `decoupechannel`
- source plotting

## Inputs

Typical source-test input directory:

```text
input/<run_name>/
├── Run_Settings.txt
├── hitsHistogram.txt
├── logfile.txt
├── <run_name>.bin
└── <run_name>.bin_0001
```

## Outputs

### hitsHistogram Analysis

The fallback analysis writes to:

```text
../output/hitsHistogram/<run_name>/
```

Files:

- `<run_name>_layer0_hitsHistogram_map.pdf`
- `<run_name>_layer0_hitsHistogram.npz`
- `<run_name>_layer0_hitsHistogram_summary.json`

### Source Raw ROOT Conversion

The source raw converter writes to:

```text
../output/source_raw/<run_name>/
```

Files:

- `<run_name>_source_raw.root`
- `<run_name>_source_raw.summary.json`

### Full Pipeline

The full source pipeline writes to:

```text
../output/pipeline/<run_name>/
```

## Plot Settings

Source-test plots use:

- PDF output
- title format `Source_test_2026_00x_thxxx`
- x-axis label font size `20`
- y-axis label font size `20`
