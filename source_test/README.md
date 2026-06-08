# Source Test

Source-test workflow for ECAL-alone data.

## Purpose

This workflow converts source-test decoded frames into the same `siwecaldecoded` ROOT structure used by the beam-test chain, so the data can be reused for:

- source hit and fraction maps
- signal maps
- pedestal studies
- later custom studies based on ROOT or `decoupechannel`

## Supported Inputs

A source run directory may contain:

- `Run_Settings.txt`
- `hitsHistogram.txt`
- `<run_name>.bin`
- `<run_name>.bin_0001`, `<run_name>.bin_0002`, ...
- or `<run_name>.dat`

## Main Commands

### Quick `hitsHistogram` fallback

```bash
./run_hits_histogram_fallback.sh \
  ../input/source_asu_2026_004_th250_run_000008 \
  0
```

### Convert source files to ROOT

```bash
./run_source_raw_converter.sh \
  ../input/source_asu_2026_004_th250_run_000008
```

Equivalent direct command:

```bash
python ../scripts/convert_source_binary_to_root.py \
  --input-dir ../input/source_asu_2026_004_th250_run_000008 \
  --output-root ../output/source_raw/source_asu_2026_004_th250_run_000008/source_asu_2026_004_th250_run_000008_siwecaldecoded.root
```

### Convert ROOT to `decoupechannel`

```bash
python ../scripts/convert_root_to_npy.py \
  --run-dir ../output/source_raw/source_asu_2026_004_th250_run_000008 \
  --layers 0
```

### Analyze one source run

```bash
python ../scripts/analyze_source_run.py \
  --run-dir ../output/source_raw/source_asu_2026_004_th250_run_000008 \
  --layer 0 \
  --settings-file ../input/source_asu_2026_004_th250_run_000008/Run_Settings.txt \
  --output-dir ../output/source/source_asu_2026_004_th250_run_000008
```

### Reuse the pedestal workflow

```bash
python ../scripts/analyze_pedestal.py \
  --run source_asu_2026_004_th250_run_000008 \
  --layer 0 \
  --memory -1 \
  --converted-base ../output/source_raw \
  --output-dir ../output/pedestal_source
```

### Full source pipeline

```bash
../run_source_pipeline.sh \
  ../input/source_asu_2026_004_th250_run_000008 \
  0
```

## Output Structure

### ROOT conversion

```text
../output/source_raw/<run_name>/
├── <run_name>_siwecaldecoded.root
└── <run_name>_siwecaldecoded.summary.json
```

### Full pipeline

```text
../output/pipeline/<run_name>/
├── analysis/
├── converted/
│   ├── <run_name>_siwecaldecoded.root
│   └── decoupechannel/
└── ...
```

### Fallback `hitsHistogram` analysis

```text
../output/hitsHistogram/<run_name>/
├── <run_name>_layer0_hitsHistogram_map.pdf
├── <run_name>_layer0_hitsHistogram.npz
└── <run_name>_layer0_hitsHistogram_summary.json
```

## Plot Settings

Source-test plots use:

- PDF output
- title format `Source_test_2026_00x_thxxx`
- x-axis title size `20`
- y-axis title size `20`
