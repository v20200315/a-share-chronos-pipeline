from __future__ import annotations

import logging

import pandas as pd

from factor_pipeline.io.loader import REQUIRED_COLUMNS

logger = logging.getLogger(__name__)


class MarketDataValidationError(ValueError):
    """Raised when OHLCV business-rule validation fails."""


class MarketDataCleaner:
    """Validate and standardize raw OHLCV market data before factor generation."""

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean a raw market-data DataFrame.

        Args:
            df: Raw market-data DataFrame loaded by ``loader.py``.

        Returns:
            A cleaned copy with standardized dates, sorted rows, duplicates removed,
            and validated OHLCV business rules. NaN values are preserved.

        Raises:
            ValueError: If required columns are missing.
            MarketDataValidationError: If OHLCV business-rule validation fails.
        """
        logger.info('loaded %d rows', len(df))
        _validate_required_columns(df)

        cleaned = df.copy()
        cleaned['date'] = _standardize_dates(cleaned['date'])
        cleaned = cleaned.sort_values('date', ascending=True).reset_index(drop=True)
        cleaned, removed_count = _remove_duplicates(cleaned)
        if removed_count:
            logger.info('removed %d duplicate rows', removed_count)

        _validate_ohlcv_rules(cleaned)
        logger.info('validation passed for %d rows', len(cleaned))
        return cleaned


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw market data using the default ``MarketDataCleaner``.

    Args:
        df: Raw market-data DataFrame.

    Returns:
        A validated and standardized DataFrame.
    """
    return MarketDataCleaner().clean(df)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'market data missing required columns: {missing_columns}')


def _standardize_dates(dates: pd.Series) -> pd.Series:
    return pd.to_datetime(dates, errors='raise')


def _remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    row_count_before = len(df)
    deduplicated = df.drop_duplicates(subset=['code', 'date'], keep='first').reset_index(drop=True)
    removed_count = row_count_before - len(deduplicated)
    return deduplicated, removed_count


def _validate_ohlcv_rules(df: pd.DataFrame) -> None:
    validators: tuple[tuple[str, pd.Series], ...] = (
        ('high >= max(open, close)', _invalid_high_vs_open_close(df)),
        ('low <= min(open, close)', _invalid_low_vs_open_close(df)),
        ('high >= low', _invalid_high_vs_low(df)),
        ('close > 0', _invalid_close(df)),
        ('volume >= 0', _invalid_non_negative(df, 'volume')),
        ('turnover >= 0', _invalid_non_negative(df, 'turnover')),
    )

    for rule_name, invalid_mask in validators:
        if invalid_mask.any():
            sample = df.loc[invalid_mask, ['code', 'date']].head(3)
            raise MarketDataValidationError(
                f'{rule_name} validation failed for {int(invalid_mask.sum())} row(s); '
                f'samples: {sample.to_dict(orient="records")}'
            )


def _invalid_high_vs_open_close(df: pd.DataFrame) -> pd.Series:
    mask = df[['open', 'high', 'close']].notna().all(axis=1)
    invalid = pd.Series(False, index=df.index)
    if mask.any():
        upper_bound = df.loc[mask, ['open', 'close']].max(axis=1)
        invalid.loc[mask] = df.loc[mask, 'high'].to_numpy() < upper_bound.to_numpy()
    return invalid


def _invalid_low_vs_open_close(df: pd.DataFrame) -> pd.Series:
    mask = df[['open', 'low', 'close']].notna().all(axis=1)
    invalid = pd.Series(False, index=df.index)
    if mask.any():
        lower_bound = df.loc[mask, ['open', 'close']].min(axis=1)
        invalid.loc[mask] = df.loc[mask, 'low'].to_numpy() > lower_bound.to_numpy()
    return invalid


def _invalid_high_vs_low(df: pd.DataFrame) -> pd.Series:
    mask = df[['high', 'low']].notna().all(axis=1)
    invalid = pd.Series(False, index=df.index)
    if mask.any():
        invalid.loc[mask] = df.loc[mask, 'high'].to_numpy() < df.loc[mask, 'low'].to_numpy()
    return invalid


def _invalid_close(df: pd.DataFrame) -> pd.Series:
    return df['close'].notna() & (df['close'] <= 0)


def _invalid_non_negative(df: pd.DataFrame, column: str) -> pd.Series:
    return df[column].notna() & (df[column] < 0)
