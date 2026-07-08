import numpy as np
import pandas as pd
import pytest

from factor_pipeline.factors.volume import (
    VOLUME_FACTOR_COLUMNS,
    VolumeFactorGenerator,
    compute_volume_factors,
)
from factor_pipeline.io.loader import REQUIRED_COLUMNS


def _cleaned_frame(code: str = '600000', rows: int = 80) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 20.0, rows) + np.sin(np.arange(rows) / 3)
    volume = np.arange(rows, dtype=float) + 1000
    turnover = np.full(rows, 0.5)
    return pd.DataFrame(
        {
            'code': code,
            'date': dates,
            'open': close - 0.1,
            'high': close + 0.5,
            'low': close - 0.5,
            'close': close,
            'volume': volume,
            'amount': close * volume,
            'amplitude': 1.0,
            'pct_change': 0.01,
            'change': 0.1,
            'turnover': turnover,
        },
        columns=list(REQUIRED_COLUMNS),
    )


def test_volume_factor_generator_appends_volume_and_turnover_factors():
    daily = _cleaned_frame()
    original_columns = list(daily.columns)

    result = VolumeFactorGenerator().generate(daily)

    assert list(result.columns) == [*original_columns, *VOLUME_FACTOR_COLUMNS]
    assert len(result) == len(daily)
    assert result.index.equals(daily.index)
    pd.testing.assert_frame_equal(result[original_columns], daily)

    volume = daily['volume']
    turnover = daily['turnover']
    volume_ma_5 = volume.rolling(5).mean()

    pd.testing.assert_series_equal(
        result['volume_change_1d'],
        volume / volume.shift(1) - 1,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['volume_change_5d'],
        volume / volume.shift(5) - 1,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['volume_ma_5'],
        volume_ma_5,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['volume_ma_10'],
        volume.rolling(10).mean(),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['volume_ratio_5'],
        volume / volume_ma_5,
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['turnover_ma_5'],
        turnover.rolling(5).mean(),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result['turnover_change_1d'],
        turnover / turnover.shift(1) - 1,
        check_names=False,
    )


def test_volume_factor_generator_preserves_leading_nans():
    daily = _cleaned_frame()

    result = VolumeFactorGenerator().generate(daily)

    assert result['volume_change_1d'].isna().iloc[0]
    assert result['volume_change_5d'].isna().iloc[:5].all()
    assert result['volume_ma_5'].isna().iloc[:4].all()
    assert result['volume_ma_10'].isna().iloc[:9].all()
    assert result['volume_ratio_5'].isna().iloc[:4].all()
    assert result['turnover_change_1d'].isna().iloc[0]
    assert not result['volume_change_1d'].isna().iloc[-1]
    assert not result['volume_ma_5'].isna().iloc[-1]
    assert not result['volume_ratio_5'].isna().iloc[-1]
    assert not result['turnover_ma_5'].isna().iloc[-1]


def test_compute_volume_factors_delegates_to_generator():
    daily = _cleaned_frame(rows=40)

    result = compute_volume_factors(daily)

    assert list(result.columns) == [*daily.columns, *VOLUME_FACTOR_COLUMNS]


def test_volume_factor_generator_raises_when_volume_missing():
    daily = _cleaned_frame().drop(columns=['volume'])

    with pytest.raises(ValueError, match='missing required columns'):
        VolumeFactorGenerator().generate(daily)


def test_volume_factor_generator_raises_when_turnover_missing():
    daily = _cleaned_frame().drop(columns=['turnover'])

    with pytest.raises(ValueError, match='missing required columns'):
        VolumeFactorGenerator().generate(daily)


def test_volume_factor_generator_raises_when_columns_already_exist():
    daily = _cleaned_frame(rows=40)
    daily['volume_change_1d'] = 0.0

    with pytest.raises(ValueError, match='would overwrite existing columns'):
        VolumeFactorGenerator().generate(daily)
