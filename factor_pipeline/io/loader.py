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
    """Resolved market-data snapshot metadata from ``manifest.json``."""

    snapshot_dir: Path
    manifest: dict[str, Any]
    daily_bars_dir: Path

    @property
    def symbols(self) -> list[str]:
        """Stock codes listed in the snapshot manifest."""
        raw_symbols = self.manifest.get('symbols', [])
        return [str(symbol).zfill(6) for symbol in raw_symbols]

    @property
    def metadata_path(self) -> Path:
        """Path to the snapshot metadata parquet file."""
        raw_path = self.manifest.get('metadata_path')
        if raw_path:
            return Path(raw_path)
        return self.snapshot_dir / 'stock_basic.parquet'


def load_snapshot(snapshot_dir: str | Path = MARKET_DATA_SNAPSHOT_LATEST) -> MarketDataSnapshot:
    """Load a market-data snapshot manifest and resolve its paths.

    Args:
        snapshot_dir: Snapshot directory containing ``manifest.json``.

    Returns:
        Resolved snapshot metadata including daily-bars directory and symbols.

    Raises:
        FileNotFoundError: If the manifest or daily-bars directory is missing.
        ValueError: If the manifest does not list any symbols.
    """
    snapshot_path = Path(snapshot_dir)
    manifest_path = snapshot_path / 'manifest.json'
    if not manifest_path.exists():
        raise FileNotFoundError(f'market data snapshot manifest not found: {manifest_path}')

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    daily_bars_dir = _resolve_manifest_path(
        manifest.get('daily_bars_path'),
        fallback=snapshot_path / 'daily_bars',
    )
    if not daily_bars_dir.exists():
        raise FileNotFoundError(f'daily bars directory not found: {daily_bars_dir}')

    snapshot = MarketDataSnapshot(
        snapshot_dir=snapshot_path,
        manifest=manifest,
        daily_bars_dir=daily_bars_dir,
    )
    if not snapshot.symbols:
        raise ValueError(f'snapshot manifest contains no symbols: {manifest_path}')

    return snapshot


def load_market_data(symbol: str, *, snapshot: MarketDataSnapshot) -> pd.DataFrame:
    """Load one symbol's daily market-data parquet file from a snapshot.

    Args:
        symbol: Stock code, for example ``"600000"`` or ``"1"``.
        snapshot: Preloaded snapshot metadata from ``load_snapshot()``.

    Returns:
        A pandas DataFrame with the parquet schema preserved.

    Raises:
        FileNotFoundError: If the parquet file for ``symbol`` does not exist.
        ValueError: If the parquet file is missing one or more required columns.
    """
    normalized_symbol = str(symbol).zfill(6)
    parquet_path = snapshot.daily_bars_dir / f'{normalized_symbol}.parquet'
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


def _resolve_manifest_path(raw_path: str | Path | None, *, fallback: Path) -> Path:
    if raw_path is None:
        return fallback
    return Path(raw_path)
