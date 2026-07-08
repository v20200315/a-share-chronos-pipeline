from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = ('volume', 'turnover')

VOLUME_CHANGE_COLUMNS: tuple[str, ...] = ('volume_change_1d', 'volume_change_5d')
VOLUME_MA_COLUMNS: tuple[str, ...] = ('volume_ma_5', 'volume_ma_10')
VOLUME_RATIO_COLUMNS: tuple[str, ...] = ('volume_ratio_5',)
TURNOVER_COLUMNS: tuple[str, ...] = ('turnover_ma_5', 'turnover_change_1d')
VOLUME_FACTOR_COLUMNS: tuple[str, ...] = (
    *VOLUME_CHANGE_COLUMNS,
    *VOLUME_MA_COLUMNS,
    *VOLUME_RATIO_COLUMNS,
    *TURNOVER_COLUMNS,
)


class VolumeFactorGenerator:
    """Generate volume- and liquidity-related factor columns from market data."""

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append volume and turnover factor columns to a market-data DataFrame.

        Args:
            df: Validated market-data DataFrame produced by upstream pipeline stages.

        Returns:
            A new DataFrame with original columns plus volume change, volume moving
            average, volume ratio, and turnover feature columns. Row order and index
            are preserved.

        Raises:
            ValueError: If required columns are missing or volume factor columns
                already exist.
        """
        _validate_required_columns(df)
        _validate_new_columns(df, VOLUME_FACTOR_COLUMNS)

        result = df.copy()
        result = self._add_volume_change(result)
        logger.info('Volume change factors generated')
        result = self._add_volume_ma(result)
        logger.info('Volume moving averages generated')
        result = self._add_volume_ratio(result)
        logger.info('Volume ratio generated')
        result = self._add_turnover_features(result)
        logger.info('Turnover factors generated')
        logger.info('Volume factors completed')
        return result

    def _add_volume_change(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append volume change columns using vectorized volume ratios.

        Args:
            df: Input DataFrame containing ``volume``.

        Returns:
            A new DataFrame with ``volume_change_1d`` and ``volume_change_5d`` appended.
        """
        volume = df['volume']
        result = df.copy()
        result['volume_change_1d'] = volume / volume.shift(1) - 1
        result['volume_change_5d'] = volume / volume.shift(5) - 1
        return result

    def _add_volume_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append volume moving-average columns using rolling means.

        Args:
            df: Input DataFrame containing ``volume``.

        Returns:
            A new DataFrame with ``volume_ma_5`` and ``volume_ma_10`` appended.
        """
        volume = df['volume']
        result = df.copy()
        result['volume_ma_5'] = volume.rolling(5).mean()
        result['volume_ma_10'] = volume.rolling(10).mean()
        return result

    def _add_volume_ratio(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append volume ratio column relative to the 5-day volume moving average.

        Args:
            df: Input DataFrame containing ``volume`` and ``volume_ma_5``.

        Returns:
            A new DataFrame with ``volume_ratio_5`` appended.
        """
        result = df.copy()
        result['volume_ratio_5'] = df['volume'] / df['volume_ma_5']
        return result

    def _add_turnover_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append turnover moving-average and change columns.

        Args:
            df: Input DataFrame containing ``turnover``.

        Returns:
            A new DataFrame with ``turnover_ma_5`` and ``turnover_change_1d`` appended.
        """
        turnover = df['turnover']
        result = df.copy()
        result['turnover_ma_5'] = turnover.rolling(5).mean()
        result['turnover_change_1d'] = turnover / turnover.shift(1) - 1
        return result


def compute_volume_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Generate volume factors using the default ``VolumeFactorGenerator``.

    Args:
        df: Market-data DataFrame after price factors.

    Returns:
        A DataFrame with volume-derived factor columns appended.
    """
    return VolumeFactorGenerator().generate(df)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'volume factors missing required columns: {missing_columns}')


def _validate_new_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    existing_columns = [column for column in columns if column in df.columns]
    if existing_columns:
        raise ValueError(f'volume factors would overwrite existing columns: {existing_columns}')
