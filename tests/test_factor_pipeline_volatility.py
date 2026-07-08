import numpy as np
import pandas as pd
import pytest
import talib

from factor_pipeline.factors.volatility import (
    TRADING_DAYS_PER_YEAR,
    VOLATILITY_FACTOR_COLUMNS,
    VolatilityFactorGenerator,
    compute_volatility_factors,
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


def test_volatility_factor_generator_appends_rolling_historical_and_atr_factors():
    daily = _cleaned_frame()
    original_columns = list(daily.columns)

    result = VolatilityFactorGenerator().generate(daily)

    assert list(result.columns) == [*original_columns, *VOLATILITY_FACTOR_COLUMNS]
    assert len(result) == len(daily)
    assert result.index.equals(daily.index)
    pd.testing.assert_frame_equal(result[original_columns], daily)

    daily_return = daily['close'].pct_change()
    pd.testing.assert_series_equal(
        result['rolling_std_5'],
        daily_return.rolling(5).std(),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['rolling_std_10'],
        daily_return.rolling(10).std(),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['historical_volatility_20'],
        daily_return.rolling(20).std() * np.sqrt(TRADING_DAYS_PER_YEAR),
        check_names=False,
    )

    expected_atr = talib.ATR(
        daily['high'].to_numpy(dtype=np.float64),
        daily['low'].to_numpy(dtype=np.float64),
        daily['close'].to_numpy(dtype=np.float64),
        timeperiod=14,
    )
    np.testing.assert_allclose(result['atr_14'].to_numpy(), expected_atr, equal_nan=True)


def test_volatility_factor_generator_preserves_leading_nans():
    daily = _cleaned_frame()

    result = VolatilityFactorGenerator().generate(daily)

    assert result['rolling_std_5'].isna().iloc[:5].all()
    assert result['rolling_std_10'].isna().iloc[:10].all()
    assert result['historical_volatility_20'].isna().iloc[:20].all()
    assert result['atr_14'].isna().iloc[0]
    assert not result['rolling_std_5'].isna().iloc[-1]
    assert not result['historical_volatility_20'].isna().iloc[-1]
    assert not result['atr_14'].isna().iloc[-1]


def test_compute_volatility_factors_delegates_to_generator():
    daily = _cleaned_frame(rows=40)

    result = compute_volatility_factors(daily)

    assert list(result.columns) == [*daily.columns, *VOLATILITY_FACTOR_COLUMNS]


def test_volatility_factor_generator_raises_when_high_missing():
    daily = _cleaned_frame().drop(columns=['high'])

    with pytest.raises(ValueError, match='missing required columns'):
        VolatilityFactorGenerator().generate(daily)


def test_volatility_factor_generator_raises_when_low_missing():
    daily = _cleaned_frame().drop(columns=['low'])

    with pytest.raises(ValueError, match='missing required columns'):
        VolatilityFactorGenerator().generate(daily)


def test_volatility_factor_generator_raises_when_close_missing():
    daily = _cleaned_frame().drop(columns=['close'])

    with pytest.raises(ValueError, match='missing required columns'):
        VolatilityFactorGenerator().generate(daily)


def test_volatility_factor_generator_raises_when_columns_already_exist():
    daily = _cleaned_frame(rows=40)
    daily['atr_14'] = 0.0

    with pytest.raises(ValueError, match='would overwrite existing columns'):
        VolatilityFactorGenerator().generate(daily)
