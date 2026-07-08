from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import talib

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = ('high', 'low', 'close')

ROLLING_STD_COLUMNS: tuple[str, ...] = ('rolling_std_5', 'rolling_std_10')
HISTORICAL_VOLATILITY_COLUMNS: tuple[str, ...] = ('historical_volatility_20',)
ATR_COLUMNS: tuple[str, ...] = ('atr_14',)
VOLATILITY_FACTOR_COLUMNS: tuple[str, ...] = (
    *ROLLING_STD_COLUMNS,
    *HISTORICAL_VOLATILITY_COLUMNS,
    *ATR_COLUMNS,
)

TRADING_DAYS_PER_YEAR = 252
ATR_PERIOD = 14


class VolatilityFactorGenerator:
    """Generate volatility-related factor columns from market data."""

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append rolling volatility, historical volatility, and ATR columns.

        Args:
            df: Validated market-data DataFrame produced by upstream pipeline stages.

        Returns:
            A new DataFrame with original columns plus ``rolling_std_5``,
            ``rolling_std_10``, ``historical_volatility_20``, and ``atr_14``.
            Row order and index are preserved.

        Raises:
            ValueError: If required columns are missing or volatility factor columns
                already exist.
        """
        _validate_required_columns(df)
        _validate_new_columns(df, VOLATILITY_FACTOR_COLUMNS)

        result = df.copy()
        result = self._add_rolling_std(result)
        logger.info('Rolling volatility generated')
        result = self._add_historical_volatility(result)
        logger.info('Historical volatility generated')
        result = self._add_atr(result)
        logger.info('ATR generated')
        logger.info('Volatility factors completed')
        return result

    def _add_rolling_std(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append rolling standard deviation of daily returns.

        Args:
            df: Input DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``rolling_std_5`` and ``rolling_std_10`` appended.
        """
        daily_return = df['close'].pct_change()
        result = df.copy()
        result['rolling_std_5'] = daily_return.rolling(5).std()
        result['rolling_std_10'] = daily_return.rolling(10).std()
        return result

    def _add_historical_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append annualized historical volatility from 20-day rolling return std.

        Args:
            df: Input DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``historical_volatility_20`` appended.
        """
        daily_return = df['close'].pct_change()
        result = df.copy()
        result['historical_volatility_20'] = daily_return.rolling(20).std() * np.sqrt(
            TRADING_DAYS_PER_YEAR
        )
        return result

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append ATR indicator column using TA-Lib default parameters.

        Args:
            df: Input DataFrame containing ``high``, ``low``, and ``close``.

        Returns:
            A new DataFrame with ``atr_14`` appended.
        """
        high = df['high'].to_numpy(dtype=np.float64)
        low = df['low'].to_numpy(dtype=np.float64)
        close = df['close'].to_numpy(dtype=np.float64)
        atr = talib.ATR(high, low, close, timeperiod=ATR_PERIOD)

        result = df.copy()
        result['atr_14'] = atr
        return result


def compute_volatility_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Generate volatility factors using the default ``VolatilityFactorGenerator``.

    Args:
        df: Market-data DataFrame after volume factors.

    Returns:
        A DataFrame with volatility-derived factor columns appended.
    """
    return VolatilityFactorGenerator().generate(df)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'volatility factors missing required columns: {missing_columns}')


def _validate_new_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    existing_columns = [column for column in columns if column in df.columns]
    if existing_columns:
        raise ValueError(f'volatility factors would overwrite existing columns: {existing_columns}')
