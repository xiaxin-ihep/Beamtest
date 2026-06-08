# ECAL Test Analysis

Reusable analysis framework for SiW-ECAL beam tests and source tests.

## Purpose

This repository provides one shared analysis structure for:

- conversion from detector data files to ROOT and `decoupechannel` NumPy arrays
- hit, pedestal, signal, and hold-scan studies
- source-test occupancy and source-response plots
- common mapping, plotting, and I/O helpers

## Repository Layout

```text
ECAL_Test_Analysis/
├── beam_test/
├── input/
├── output/
├── run_source_pipeline.sh
├── scripts/
├── siwecal_analysis/
└── source_test/
```

Key directories:

- `scripts/`: command-line entry points
- `siwecal_analysis/`: shared Python modules
- `beam_test/`: beam-test usage notes
- `source_test/`: source-test usage notes
- `input/`: run directories
- `output/`: analysis products

## Environment

Use the ROOT and `uproot` environment:

```bash
conda activate r6.28
```

Quick check:

```bash
python -c "import numpy, matplotlib, uproot, ROOT"
```

## Data Flow

### Beam Test

```text
binary/ROOT input
  -> converted ROOT
  -> decoupechannel/layerX/*.npy
  -> pedestal / hit map / signal / SNR / hold scan
```

### Source Test

```text
source .bin/.bin_XXXX or .dat
  -> siwecaldecoded ROOT
  -> decoupechannel/layerX/*.npy
  -> source hit / fraction / signal plots
  -> pedestal or other beam-style studies if needed
```

## Beam Test Workflow

Main scripts:

- `scripts/convert_binary_to_root.py`
- `scripts/convert_root_to_npy.py`
- `scripts/analyze_pedestal.py`
- `scripts/analyze_hit_map.py`
- `scripts/analyze_signal_map.py`
- `scripts/analyze_hold_scan.py`

Typical usage:

```bash
python scripts/analyze_pedestal.py \
  --run 587 \
  --layer 1 \
  --memory 0
```

```bash
python scripts/analyze_hit_map.py \
  --run 587 \
  --layer 1 \
  --memory -1
```

```bash
python scripts/analyze_signal_map.py \
  --run 587 \
  --layer 1 \
  --memory 0 \
  --pedestal-file output/pedestal/<pedestal_file>.npz
```

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

Beam-test inputs:

- converted ROOT files with tree `siwecaldecoded`
- or `decoupechannel/layerX/*.npy`

Beam-test outputs:

- `output/pedestal/`
- `output/hitmap/`
- `output/signal/`
- `output/hold_scan/`

## Source Test Workflow

Main scripts:

- `scripts/convert_source_binary_to_root.py`
- `scripts/convert_root_to_npy.py`
- `scripts/analyze_source_run.py`
- `scripts/analyze_pedestal.py`
- `scripts/analyze_hits_histogram.py`
- `scripts/analyze_source_campaign.py`
- `scripts/run_source_pipeline.py`
- `run_source_pipeline.sh`

Supported source input files:

- `*.bin`
- `*.bin_XXXX`
- `*.dat`
- optional `Run_Settings.txt`
- optional `hitsHistogram.txt`

### 1. Convert source data to ROOT

```bash
python scripts/convert_source_binary_to_root.py \
  --input-dir input/source_asu_2026_002_th250_run_000009 \
  --output-root output/source_raw/source_asu_2026_002_th250_run_000009/source_asu_2026_002_th250_run_000009_siwecaldecoded.root
```

This writes a beam-test-like ROOT tree named `siwecaldecoded`.

### 2. Convert ROOT to `decoupechannel`

```bash
python scripts/convert_root_to_npy.py \
  --run-dir output/source_raw/source_asu_2026_002_th250_run_000009 \
  --layers 0
```

### 3. Produce source plots

```bash
python scripts/analyze_source_run.py \
  --run-dir output/source_raw/source_asu_2026_002_th250_run_000009 \
  --layer 0 \
  --settings-file input/source_asu_2026_002_th250_run_000009/Run_Settings.txt \
  --output-dir output/source/source_asu_2026_002_th250_run_000009
```

### 4. Run pedestal analysis on source data

After step 2, the standard pedestal code can be reused:

```bash
python scripts/analyze_pedestal.py \
  --run source_asu_2026_002_th250_run_000009 \
  --layer 0 \
  --memory -1 \
  --converted-base output/source_raw \
  --output-dir output/pedestal_source
```

### 5. Run the full source pipeline

```bash
./run_source_pipeline.sh \
  input/source_asu_2026_002_th250_run_000009 \
  0
```

This performs:

- source file conversion to `siwecaldecoded` ROOT
- ROOT to `decoupechannel`
- source response plots

## Input Structure

Typical source run directory:

```text
input/<run_name>/
├── Run_Settings.txt
├── hitsHistogram.txt
├── <run_name>.bin
├── <run_name>.bin_0001
└── ...
```

or:

```text
input/<run_name>/
├── Run_Settings.txt
├── hitsHistogram.txt
└── <run_name>.dat
```

## Output Structure

Common output products:

- converted ROOT with tree `siwecaldecoded`
- `decoupechannel/layerX/*.npy`
- pedestal `.npz`
- source hit / fraction / signal PDFs
- JSON summaries

Typical source pipeline output:

```text
output/pipeline/<run_name>/
├── analysis/
├── converted/
│   ├── <run_name>_siwecaldecoded.root
│   └── decoupechannel/
└── pedestal/   # optional, if run separately
```

## Plot Conventions

Source-test plotting defaults:

- PDF output
- title format `Source_test_2026_00x_thxxx`
- x-axis title size `20`
- y-axis title size `20`

## References

- [beam_test/README.md](/Users/xiaxin/Desktop/work/TB_Desy/TB2025-03/SiWECAL-TB-analysis/script_victor_cp/local_analysis/ECAL_Test_Analysis/beam_test/README.md:1)
- [source_test/README.md](/Users/xiaxin/Desktop/work/TB_Desy/TB2025-03/SiWECAL-TB-analysis/script_victor_cp/local_analysis/ECAL_Test_Analysis/source_test/README.md:1)
