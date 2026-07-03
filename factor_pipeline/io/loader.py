from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.dataset as ds

from factor_pipeline.paths import MARKET_DATA_SNAPSHOT_LATEST

REQUIRED_COLUMNS: tuple[str, ...] = (
    'date',
    'code',
    'open',
    'high',
    'low',
    'close',
    'volume',
    'amount',
    'amplitude',
    'pct_change',
    'change',
    'turnover',
)


@dataclass(frozen=True)
class MarketDataSnapshot:
    """Resolved market-data snapshot metadata."""

    snapshot_dir: Path
    manifest: dict[str, Any]
    daily_bars_dir: Path


def load_snapshot(snapshot_dir: str | Path = MARKET_DATA_SNAPSHOT_LATEST) -> MarketDataSnapshot:
    """Load a market-data snapshot manifest and resolve its daily-bars directory.

    Args:
        snapshot_dir: Snapshot directory containing ``manifest.json``.

    Returns:
        Resolved snapshot metadata including the daily-bars directory.

    Raises:
        FileNotFoundError: If the manifest or daily-bars directory is missing.
    """
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


def load_market_data(
    symbol: str,
    *,
    snapshot: MarketDataSnapshot | None = None,
    daily_bars_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Load one symbol's daily market-data parquet file.

    Args:
        symbol: Stock code, for example ``"600000"`` or ``"1"``.
        snapshot: Optional preloaded snapshot metadata.
        daily_bars_dir: Optional override for the daily-bars directory, used
            when no snapshot has been published yet.

    Returns:
        A pandas DataFrame with the parquet schema preserved.

    Raises:
        FileNotFoundError: If the parquet file for ``symbol`` does not exist.
        ValueError: If the parquet file is missing one or more required columns.
    """
    source_dir = (
        Path(daily_bars_dir) if daily_bars_dir is not None else _snapshot_daily_dir(snapshot)
    )
    parquet_path = source_dir / f'{str(symbol).zfill(6)}.parquet'
    if not parquet_path.exists():
        raise FileNotFoundError(f'market data parquet not found: {parquet_path}')

    dataset = ds.dataset(parquet_path, format='parquet')
    validate_required_columns(dataset.schema.names)

    table = dataset.to_table()
    return table.to_pandas()


def validate_required_columns(column_names: list[str]) -> None:
    """Validate that all required market-data columns are present.

    Args:
        column_names: Column names read from the parquet dataset schema.

    Raises:
        ValueError: If any required column is missing.
    """
    available_columns = set(column_names)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in available_columns]
    if missing_columns:
        raise ValueError(f'market data parquet missing required columns: {missing_columns}')


def _snapshot_daily_dir(snapshot: MarketDataSnapshot | None) -> Path:
    if snapshot is None:
        snapshot = load_snapshot()
    return snapshot.daily_bars_dir
