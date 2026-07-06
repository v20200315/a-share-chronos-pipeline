from __future__ import annotations

from pathlib import Path

MARKET_DATA_SNAPSHOT_LATEST = Path('data/market_data/snapshots/latest')
FACTOR_INPUT_DIR = MARKET_DATA_SNAPSHOT_LATEST / 'daily_bars'
FACTOR_OUTPUT_DIR = Path('data/factor_pipeline/output')
