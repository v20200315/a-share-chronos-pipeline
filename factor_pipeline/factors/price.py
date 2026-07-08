from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = ('close',)

RETURN_COLUMNS: tuple[str, ...] = ('return_1d', 'return_5d', 'return_10d')
MOMENTUM_COLUMNS: tuple[str, ...] = ('momentum_5d', 'momentum_10d')
PRICE_FACTOR_COLUMNS: tuple[str, ...] = (*RETURN_COLUMNS, *MOMENTUM_COLUMNS)


class PriceFactorGenerator:
    """Generate price-derived factor columns from cleaned market data."""

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append daily returns and price momentum columns to a market-data DataFrame.

        Args:
            df: Validated market-data DataFrame produced by upstream pipeline stages.

        Returns:
            A new DataFrame with original columns plus ``return_1d``, ``return_5d``,
            ``return_10d``, ``momentum_5d``, and ``momentum_10d``. Row order and
            index are preserved.

        Raises:
            ValueError: If ``close`` is missing or price factor columns already exist.
        """
        _validate_required_columns(df)
        _validate_new_columns(df, PRICE_FACTOR_COLUMNS)

        result = df.copy()
        result = self._add_returns(result)
        logger.info('Returns generated')
        result = self._add_momentum(result)
        logger.info('Momentum generated')
        logger.info('Price factors completed')
        return result

    def _add_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append daily return columns using vectorized close-price ratios.

        Args:
            df: Input DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``return_1d``, ``return_5d``, and ``return_10d`` appended.
        """
        close = df['close']
        result = df.copy()
        result['return_1d'] = close / close.shift(1) - 1
        result['return_5d'] = close / close.shift(5) - 1
        result['return_10d'] = close / close.shift(10) - 1
        return result

    def _add_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append price momentum columns using vectorized close-price differences.

        Args:
            df: Input DataFrame containing ``close``.

        Returns:
            A new DataFrame with ``momentum_5d`` and ``momentum_10d`` appended.
        """
        close = df['close']
        result = df.copy()
        result['momentum_5d'] = close - close.shift(5)
        result['momentum_10d'] = close - close.shift(10)
        return result


def compute_price_factors(df: pd.DataFrame) -> pd.DataFrame:
    """Generate price factors using the default ``PriceFactorGenerator``.

    Args:
        df: Market-data DataFrame after technical factors.

    Returns:
        A DataFrame with price-derived factor columns appended.
    """
    return PriceFactorGenerator().generate(df)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'price factors missing required columns: {missing_columns}')


def _validate_new_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    existing_columns = [column for column in columns if column in df.columns]
    if existing_columns:
        raise ValueError(f'price factors would overwrite existing columns: {existing_columns}')
