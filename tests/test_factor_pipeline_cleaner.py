import numpy as np
import pandas as pd
import pytest

from factor_pipeline.cleaner.cleaner import MarketDataCleaner, MarketDataValidationError, clean


def _valid_frame(
    *, rows: int = 3, reverse: bool = False, duplicate_first: bool = False
) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 12.0, rows)
    df = pd.DataFrame(
        {
            'code': '600000',
            'date': dates.strftime('%Y-%m-%d'),
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
        }
    )
    if duplicate_first:
        df = pd.concat([df.iloc[[0]], df], ignore_index=True)
    if reverse:
        return df.iloc[::-1].reset_index(drop=True)
    return df


def test_market_data_cleaner_sorts_dates_and_removes_duplicates():
    cleaner = MarketDataCleaner()
    input_df = _valid_frame(rows=3, reverse=True, duplicate_first=True)

    cleaned = cleaner.clean(input_df)

    assert len(cleaned) == 3
    assert cleaned['date'].is_monotonic_increasing
    assert pd.api.types.is_datetime64_any_dtype(cleaned['date'])
    assert cleaned.iloc[0]['date'] == pd.Timestamp('2024-01-01')


def test_clean_wrapper_delegates_to_market_data_cleaner():
    input_df = _valid_frame(rows=2, reverse=True)

    cleaned = clean(input_df)

    assert cleaned['date'].is_monotonic_increasing


def test_market_data_cleaner_raises_on_invalid_high_low():
    cleaner = MarketDataCleaner()
    df = _valid_frame(rows=1)
    df.loc[0, ['open', 'close']] = np.nan
    df.loc[0, 'high'] = 5.0
    df.loc[0, 'low'] = 10.0

    with pytest.raises(MarketDataValidationError, match='high >= low'):
        cleaner.clean(df)


def test_market_data_cleaner_raises_on_non_positive_close():
    cleaner = MarketDataCleaner()
    df = _valid_frame(rows=1)
    df.loc[0, ['open', 'high', 'low']] = np.nan
    df.loc[0, 'close'] = 0.0

    with pytest.raises(MarketDataValidationError, match='close > 0'):
        cleaner.clean(df)


def test_market_data_cleaner_skips_nan_cells_during_validation():
    cleaner = MarketDataCleaner()
    df = _valid_frame(rows=2)
    df.loc[0, 'close'] = np.nan
    df.loc[1, ['open', 'high', 'low', 'close']] = [11.0, 12.0, 10.0, 11.0]

    cleaned = cleaner.clean(df)

    assert pd.isna(cleaned.loc[0, 'close'])
    assert cleaned.loc[1, 'close'] == 11.0


def test_market_data_cleaner_raises_when_required_columns_missing():
    cleaner = MarketDataCleaner()
    df = _valid_frame(rows=1).drop(columns=['volume'])

    with pytest.raises(ValueError, match='missing required columns'):
        cleaner.clean(df)
