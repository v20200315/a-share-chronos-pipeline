from __future__ import annotations

from pathlib import Path

import pandas as pd

from factor_pipeline.paths import MARKET_DATA_INPUT_DIR

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


def load_market_data(
    symbol: str,
    *,
    input_dir: str | Path = MARKET_DATA_INPUT_DIR,
) -> pd.DataFrame:
    """Load one symbol's daily market-data parquet file.

    Args:
        symbol: Stock code, for example ``"600000"`` or ``"1"``.
        input_dir: Directory containing one parquet file per symbol, named
            ``{code}.parquet``.

    Returns:
        A pandas DataFrame with the parquet schema preserved.

    Raises:
        FileNotFoundError: If the parquet file for ``symbol`` does not exist.
        ValueError: If the parquet file is missing one or more required columns.
    """
    parquet_path = _parquet_path(symbol, input_dir=Path(input_dir))
    if not parquet_path.exists():
        raise FileNotFoundError(f'market data parquet not found: {parquet_path}')

    df = pd.read_parquet(parquet_path)
    _validate_required_columns(list(df.columns))
    return df


def _parquet_path(symbol: str, *, input_dir: Path) -> Path:
    normalized_symbol = str(symbol).zfill(6)
    return input_dir / f'{normalized_symbol}.parquet'


def _validate_required_columns(column_names: list[str]) -> None:
    available_columns = set(column_names)
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in available_columns
    ]
    if missing_columns:
        raise ValueError(f'market data parquet missing required columns: {missing_columns}')
