import numpy as np
import pandas as pd
import pytest

from factor_pipeline.factors.price import (
    PRICE_FACTOR_COLUMNS,
    PriceFactorGenerator,
    compute_price_factors,
)
from factor_pipeline.io.loader import REQUIRED_COLUMNS


def _cleaned_frame(code: str = '600000', rows: int = 80) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 20.0, rows) + np.sin(np.arange(rows) / 3)
    return pd.DataFrame(
        {
            'code': code,
            'date': dates,
            'open': close - 0.1,
            'high': close + 0.5,
            'low': close - 0.5,
            'close': close,
            'volume': np.arange(rows) + 1000,
            'amount': close * (np.arange(rows) + 1000),
            'amplitude': 1.0,
            'pct_change': 0.01,
            'change': 0.1,
            'turnover': 0.5,
        },
        columns=list(REQUIRED_COLUMNS),
    )


def test_price_factor_generator_appends_returns_and_momentum():
    daily = _cleaned_frame()
    original_columns = list(daily.columns)

    result = PriceFactorGenerator().generate(daily)

    assert list(result.columns) == [*original_columns, *PRICE_FACTOR_COLUMNS]
    assert len(result) == len(daily)
    assert result.index.equals(daily.index)
    pd.testing.assert_frame_equal(result[original_columns], daily)

    close = daily['close']
    pd.testing.assert_series_equal(
        result['return_1d'],
        close / close.shift(1) - 1,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['return_5d'],
        close / close.shift(5) - 1,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['return_10d'],
        close / close.shift(10) - 1,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['momentum_5d'],
        close - close.shift(5),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['momentum_10d'],
        close - close.shift(10),
        check_names=False,
    )


def test_price_factor_generator_preserves_leading_nans():
    daily = _cleaned_frame()

    result = PriceFactorGenerator().generate(daily)

    assert result['return_1d'].isna().iloc[0]
    assert result['return_5d'].isna().iloc[:5].all()
    assert result['return_10d'].isna().iloc[:10].all()
    assert result['momentum_5d'].isna().iloc[:5].all()
    assert result['momentum_10d'].isna().iloc[:10].all()
    assert not result['return_1d'].isna().iloc[-1]
    assert not result['return_10d'].isna().iloc[-1]
    assert not result['momentum_10d'].isna().iloc[-1]


def test_compute_price_factors_delegates_to_generator():
    daily = _cleaned_frame(rows=40)

    result = compute_price_factors(daily)

    assert list(result.columns) == [*daily.columns, *PRICE_FACTOR_COLUMNS]


def test_price_factor_generator_raises_when_close_missing():
    daily = _cleaned_frame().drop(columns=['close'])

    with pytest.raises(ValueError, match='missing required columns'):
        PriceFactorGenerator().generate(daily)


def test_price_factor_generator_raises_when_columns_already_exist():
    daily = _cleaned_frame(rows=40)
    daily['return_1d'] = 0.0

    with pytest.raises(ValueError, match='would overwrite existing columns'):
        PriceFactorGenerator().generate(daily)
