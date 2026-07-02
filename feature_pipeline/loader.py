from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from feature_pipeline.paths import MARKET_DATA_SNAPSHOT_LATEST

REQUIRED_DAILY_COLUMNS = ['code', 'date', 'close']


@dataclass(frozen=True)
class MarketDataSnapshot:
    snapshot_dir: Path
    manifest: dict[str, Any]
    daily_bars_dir: Path


def load_snapshot(snapshot_dir: str | Path = MARKET_DATA_SNAPSHOT_LATEST) -> MarketDataSnapshot:
    snapshot_path = Path(snapshot_dir)
    manifest_path = snapshot_path / 'manifest.json'
    if not manifest_path.exists():
        raise FileNotFoundError(f'market data snapshot manifest not found: {manifest_path}')

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    daily_bars_dir = Path(manifest.get('daily_bars_path') or snapshot_path / 'daily_bars')
    if not daily_bars_dir.exists():
        raise FileNotFoundError(f'daily bars directory not found: {daily_bars_dir}')

    return MarketDataSnapshot(
        snapshot_dir=snapshot_path,
        manifest=manifest,
        daily_bars_dir=daily_bars_dir,
    )


def load_daily_bars(
    code: str,
    *,
    snapshot: MarketDataSnapshot | None = None,
    daily_bars_dir: str | Path | None = None,
) -> pd.DataFrame:
    source_dir = Path(daily_bars_dir) if daily_bars_dir is not None else _snapshot_daily_dir(snapshot)
    symbol = str(code).zfill(6)
    daily_path = source_dir / f'{symbol}.parquet'
    if not daily_path.exists():
        raise FileNotFoundError(f'daily bars parquet not found: {daily_path}')

    df = pd.read_parquet(daily_path)
    missing_columns = [column for column in REQUIRED_DAILY_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'daily bars missing required columns: {missing_columns}')

    normalized = df.copy()
    normalized['code'] = normalized['code'].astype(str).str.zfill(6)
    normalized['date'] = pd.to_datetime(normalized['date'], format='%Y-%m-%d', errors='raise')
    normalized['close'] = pd.to_numeric(normalized['close'], errors='raise')
    normalized = normalized.sort_values('date').reset_index(drop=True)
    normalized['date'] = normalized['date'].dt.strftime('%Y-%m-%d')
    return normalized


def _snapshot_daily_dir(snapshot: MarketDataSnapshot | None) -> Path:
    if snapshot is None:
        snapshot = load_snapshot()
    return snapshot.daily_bars_dir
