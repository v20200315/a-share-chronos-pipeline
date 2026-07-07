from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import talib

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = ('close',)

MACD_COLUMNS: tuple[str, ...] = ('macd', 'macd_signal', 'macd_hist')
RSI_COLUMN = 'rsi'
TECHNICAL_FACTOR_COLUMNS: tuple[str, ...] = (*MACD_COLUMNS, RSI_COLUMN)


class TechnicalFactorGenerator:
    """Generate technical indicator columns from cleaned market data."""

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append MACD and RSI columns to a cleaned market-data DataFrame.

        Args:
            df: Validated market-data DataFrame produced by ``cleaner.py``.

        Returns:
            A new DataFrame with original columns plus ``macd``, ``macd_signal``,
            ``macd_hist``, and ``rsi``. Row order and index are preserved.

        Raises:
            ValueError: If ``close`` is missing or technical factor columns already exist.
        """
        _validate_required_columns(df)
        _validate_new_columns(df, TECHNICAL_FACTOR_COLUMNS)

        result = df.copy()
        result = self._add_macd(result)
        logger.info('MACD generated')
        result = self._add_rsi(result)
        logger.info('RSI generated')
        logger.info('Technical factors completed')
        return result

    def _add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append MACD indicator columns using TA-Lib default parameters.

        Args:
            df: Input DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``macd``, ``macd_signal``, and ``macd_hist`` appended.
        """
        close = df['close'].to_numpy(dtype=np.float64)
        macd, macd_signal, macd_hist = talib.MACD(
            close,
            fastperiod=12,
            slowperiod=26,
            signalperiod=9,
        )

        result = df.copy()
        result['macd'] = macd
        result['macd_signal'] = macd_signal
        result['macd_hist'] = macd_hist
        return result

    def _add_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append RSI indicator column using TA-Lib default parameters.

        Args:
            df: Input DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``rsi`` appended.
        """
        close = df['close'].to_numpy(dtype=np.float64)
        rsi = talib.RSI(close, timeperiod=14)

        result = df.copy()
        result['rsi'] = rsi
        return result


def compute_technical_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Generate technical factors using the default ``TechnicalFactorGenerator``.

    Args:
        df: Cleaned market-data DataFrame.

    Returns:
        A DataFrame with technical indicator columns appended.
    """
    return TechnicalFactorGenerator().generate(df)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'technical factors missing required columns: {missing_columns}')


def _validate_new_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    existing_columns = [column for column in columns if column in df.columns]
    if existing_columns:
        raise ValueError(f'technical factors would overwrite existing columns: {existing_columns}')
