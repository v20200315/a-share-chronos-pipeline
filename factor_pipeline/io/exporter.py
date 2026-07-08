from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from factor_pipeline.paths import FACTOR_OUTPUT_DIR, validate_output_dir

logger = logging.getLogger(__name__)


class DatasetExporter:
    """Export a research dataset DataFrame to per-symbol parquet files."""

    def export(
        self,
        df: pd.DataFrame,
        symbol: str,
        output_dir: Path | str,
    ) -> Path:
        """Write one symbol's factor dataset to parquet.

        Args:
            df: Final research dataset to persist.
            symbol: Stock code used to build the output filename.
            output_dir: Directory that stores ``{symbol}_factor.parquet`` files.

        Returns:
            The path of the written parquet file.

        Raises:
            ValueError: If the DataFrame is empty, the symbol is invalid, or the
                output directory path is invalid.
            PermissionError: If the output directory exists but is not writable.
        """
        _validate_dataframe(df)
        stripped_symbol = _validate_symbol(symbol)
        output_path_input = _validate_output_dir_path(output_dir)

        logger.info('export started')
        directory_created = not output_path_input.exists()
        resolved_dir = validate_output_dir(output_path_input)
        if directory_created:
            logger.info('output directory created: %s', resolved_dir)

        normalized_symbol = stripped_symbol.zfill(6)
        output_path = resolved_dir / f'{normalized_symbol}_factor.parquet'
        logger.info('file path: %s', output_path)

        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, output_path)

        logger.info('row count: %s', len(df))
        logger.info('column count: %s', len(df.columns))
        logger.info('export completed')
        return output_path


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
    return DatasetExporter().export(df, symbol, output_dir)


def _validate_dataframe(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError('dataset export requires a non-empty DataFrame')


def _validate_symbol(symbol: str) -> str:
    stripped_symbol = str(symbol).strip()
    if not stripped_symbol:
        raise ValueError('dataset export requires a non-empty symbol')
    return stripped_symbol


def _validate_output_dir_path(output_dir: Path | str) -> Path:
    if not str(output_dir).strip():
        raise ValueError('dataset export requires a non-empty output directory')

    target = Path(output_dir)
    if target.exists() and not target.is_dir():
        raise ValueError(f'dataset export output directory is not a directory: {target}')
    return target
