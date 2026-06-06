# Beam Test

This directory documents the workflow for beam-test analysis.

## Purpose

The beam-test workflow is intended for:

- pedestal studies
- noise studies
- hit maps
- signal / amplitude maps
- S/N maps
- hold-value scans

## Main Scripts

- `../scripts/analyze_pedestal.py`
- `../scripts/analyze_hit_map.py`
- `../scripts/analyze_signal_map.py`
- `../scripts/analyze_hold_scan.py`

## Input

Beam-test analysis expects one of the following:

- a run directory with `decoupechannel/layerX/*.npy`
- a run directory with ROOT files that can be read directly

## Typical Workflow

### Pedestal

```bash
python ../scripts/analyze_pedestal.py \
  --run 587 \
  --layer 1 \
  --memory 0
```

### Hit Map

```bash
python ../scripts/analyze_hit_map.py \
  --run 587 \
  --layer 1 \
  --memory -1
```

### Signal / SNR

```bash
python ../scripts/analyze_signal_map.py \
  --run 587 \
  --layer 1 \
  --memory 0 \
  --pedestal-file ../output/pedestal/Run_ILC_20250304_masking_it3_2_eudaq_run_090587_layer1_pedestal.npz
```

### Hold Scan

```bash
python ../scripts/analyze_hold_scan.py \
  --runs 586 589 590 591 592 593 595 \
  --hold-values 50 70 90 110 130 150 170 \
  --layer 1 \
  --chip 12 \
  --memory 0 \
  --channel 13 \
  --use-hitbit 1
```

## Output

Outputs are written under the corresponding subdirectories in:

```text
../output/
```

Examples:

- `../output/pedestal/`
- `../output/hitmap/`
- `../output/signal/`
- `../output/hold_scan/`

## Notes

- `--memory -1` means “merge all memory cells”.
- Pedestal outputs store both mapped `32x32` arrays and raw `16x64` channel arrays.
