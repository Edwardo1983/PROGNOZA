# Core Package

The `core` package hosts subsystems that are shared across the PROGNOZA stack.  
At the moment it contains the `data_quality` module, which validates 1-minute Janitza CSV exports and produces QA artefacts.

## Data Quality Workflow

1. **Alignment & Integrity** – `core.data_quality.alignment` parses timestamps, enforces UTC monotonicity and checks for ±3s drift from minute boundaries.  
2. **Value Ranges** – `core.data_quality.ranges` verifies voltage, current, frequency, power factor, and THD against limits defined in `config/data_quality.yaml`.  
3. **Gap Repair** – `core.data_quality.repair` forward-fills short gaps (≤2 samples) and interpolates without altering longer-term trends.  
4. **Reporting** – `core.data_quality.report` assembles JSON + HTML summaries (with matplotlib sparklines) and is exposed via `python -m core.data_quality.report`.

## Key APIs

```python
from pathlib import Path
from core.data_quality import load_config, validate_csv, auto_repair_csv

cfg = load_config()
result = validate_csv(Path("data/exports/sample.csv"), cfg)

if not result["ok"]:
    auto_repair_csv("data/exports/sample.csv", "data/exports/sample.cleaned.csv", cfg)
```

## CLI Usage

Generate a QA bundle in place or write a repaired CSV:

```bash
# Analyse only
python -m core.data_quality.report data/exports/umg_readings_2024-01-01.csv

# Validate and repair output to a new file
python -m core.data_quality.report data/exports/umg_readings_2024-01-01.csv --repair-out data/exports/umg_readings_2024-01-01.cleaned.csv
```

The CLI writes `*.qa.json` and `*.qa.html` alongside the repaired CSV (or original file if `--no-repair` is used).

## Configuration

Tune thresholds in `config/data_quality.yaml`:

```yaml
timezone: "Europe/Bucharest"
drift_sec_max: 3
ranges:
  voltage_v: [195, 264]
  current_a: [0, 10000]
forward_fill_max: 2
```

Adjusting any of these values immediately affects both validation and repair logic. Tests covering the workflow live in `tests/test_quality.py`.
