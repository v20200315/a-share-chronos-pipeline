import numpy as np
import pandas as pd
import pytest
import talib

from factor_pipeline.factors.technical import (
    TECHNICAL_FACTOR_COLUMNS,
    TechnicalFactorGenerator,
    compute_technical_factors,
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


def test_technical_factor_generator_matches_talib_macd_and_rsi():
    daily = _cleaned_frame()
    original_columns = list(daily.columns)

    result = TechnicalFactorGenerator().generate(daily)

    assert list(result.columns) == [*original_columns, *TECHNICAL_FACTOR_COLUMNS]
    assert len(result) == len(daily)
    assert result.index.equals(daily.index)
    pd.testing.assert_frame_equal(result[original_columns], daily)

    close = daily['close'].to_numpy(dtype=np.float64)
    expected_macd, expected_signal, expected_hist = talib.MACD(close)
    expected_rsi = talib.RSI(close)
    np.testing.assert_allclose(result['macd'].to_numpy(), expected_macd, equal_nan=True)
    np.testing.assert_allclose(result['macd_signal'].to_numpy(), expected_signal, equal_nan=True)
    np.testing.assert_allclose(result['macd_hist'].to_numpy(), expected_hist, equal_nan=True)
    np.testing.assert_allclose(result['rsi'].to_numpy(), expected_rsi, equal_nan=True)
    assert result['macd'].isna().iloc[0]
    assert result['rsi'].isna().iloc[0]
    assert not result['macd'].isna().iloc[-1]
    assert not result['rsi'].isna().iloc[-1]


def test_compute_technical_factors_delegates_to_generator():
    daily = _cleaned_frame(rows=40)

    result = compute_technical_factors(daily)

    assert list(result.columns) == [*daily.columns, *TECHNICAL_FACTOR_COLUMNS]


def test_technical_factor_generator_raises_when_close_missing():
    daily = _cleaned_frame().drop(columns=['close'])

    with pytest.raises(ValueError, match='missing required columns'):
        TechnicalFactorGenerator().generate(daily)


def test_technical_factor_generator_raises_when_columns_already_exist():
    daily = _cleaned_frame(rows=40)
    daily['macd'] = 0.0

    with pytest.raises(ValueError, match='would overwrite existing columns'):
        TechnicalFactorGenerator().generate(daily)
