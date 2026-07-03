from __future__ import annotations

from pathlib import Path

import pandas as pd

from factor_pipeline.paths import FACTOR_OUTPUT_DIR


def export_factor_dataset(
    df: pd.DataFrame,
    symbol: str,
    *,
    output_dir: str | Path = FACTOR_OUTPUT_DIR,
) -> Path:
    """Save a factor dataset parquet file for one symbol.

    Args:
        df: Factor dataset to persist.
        symbol: Stock code used to build the output filename.
        output_dir: Directory that stores ``{symbol}_factor.parquet`` files.

    Returns:
        The path of the written parquet file.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    normalized_symbol = str(symbol).zfill(6)
    output_path = target_dir / f'{normalized_symbol}_factor.parquet'
    df.to_parquet(output_path, index=False)
    return output_path
