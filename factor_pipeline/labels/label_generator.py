from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = ('close',)
LABEL_COLUMNS: tuple[str, ...] = ('future_return', 'label')


class LabelGenerator:
    """Generate supervised learning labels from forward-looking close returns."""

    def __init__(self, horizon: int = 5, threshold: float = 0.02) -> None:
        """Initialize label generation parameters.

        Args:
            horizon: Number of trading days ahead for the forward return window.
            threshold: Minimum forward return required for a positive ``label``.
        """
        self._horizon = horizon
        self._threshold = threshold

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append forward return and binary label columns, then drop tail rows.

        Args:
            df: Factor-enriched market-data DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``future_return`` and ``label`` appended. The last
            ``horizon`` rows are removed because they have no observable future price.

        Raises:
            ValueError: If ``close`` is missing or label columns already exist.
        """
        _validate_required_columns(df)
        _validate_new_columns(df, LABEL_COLUMNS)

        result = df.copy()
        result = self._add_future_return(result)
        logger.info('future_return generated')
        result = self._add_binary_label(result)
        logger.info('binary labels generated')
        result = self._remove_tail_rows(result)
        logger.info('tail rows removed')
        logger.info('label generation completed')
        return result

    def _add_future_return(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append the forward return column using a negative close shift.

        Args:
            df: Input DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``future_return`` appended.
        """
        close = df['close']
        result = df.copy()
        result['future_return'] = close.shift(-self._horizon) / close - 1
        return result

    def _add_binary_label(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append a binary classification label from forward return and threshold.

        Args:
            df: Input DataFrame containing ``future_return``.

        Returns:
            A new DataFrame with ``label`` appended.
        """
        result = df.copy()
        result['label'] = (result['future_return'] >= self._threshold).astype(int)
        return result

    def _remove_tail_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop rows without an observable future price at the requested horizon.

        Args:
            df: Input DataFrame with label columns appended.

        Returns:
            A new DataFrame with the last ``horizon`` rows removed.
        """
        if self._horizon <= 0 or len(df) <= self._horizon:
            return df.iloc[0:0].copy()

        return df.iloc[:-self._horizon].copy()


def generate_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Generate labels using the default ``LabelGenerator`` configuration.

    Args:
        df: Factor-enriched market-data DataFrame.

    Returns:
        A DataFrame with ``future_return`` and ``label`` appended and tail rows removed.
    """
    return LabelGenerator().generate(df)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'label generation missing required columns: {missing_columns}')


def _validate_new_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    existing_columns = [column for column in columns if column in df.columns]
    if existing_columns:
        raise ValueError(f'label generation would overwrite existing columns: {existing_columns}')
