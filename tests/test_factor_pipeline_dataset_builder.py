import numpy as np
import pandas as pd
import pytest

from factor_pipeline.dataset.builder import (
    DATASET_COLUMNS,
    FEATURE_COLUMNS,
    METADATA_COLUMNS,
    TARGET_COLUMNS,
    DatasetBuilder,
    build_dataset,
)
from factor_pipeline.factors.price import PRICE_FACTOR_COLUMNS
from factor_pipeline.factors.technical import TECHNICAL_FACTOR_COLUMNS
from factor_pipeline.factors.volatility import VOLATILITY_FACTOR_COLUMNS
from factor_pipeline.factors.volume import VOLUME_FACTOR_COLUMNS
from factor_pipeline.io.loader import REQUIRED_COLUMNS


def _labeled_frame(rows: int = 20) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 12.0, rows)
    frame = pd.DataFrame(
        {
            'code': '600000',
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

    for index, column in enumerate(TECHNICAL_FACTOR_COLUMNS):
        frame[column] = np.arange(rows, dtype=float) + index
    for index, column in enumerate(PRICE_FACTOR_COLUMNS):
        frame[column] = np.arange(rows, dtype=float) + 10 + index
    for index, column in enumerate(VOLUME_FACTOR_COLUMNS):
        frame[column] = np.arange(rows, dtype=float) + 20 + index
    for index, column in enumerate(VOLATILITY_FACTOR_COLUMNS):
        frame[column] = np.arange(rows, dtype=float) + 30 + index

    frame['future_return'] = np.linspace(0.0, 0.05, rows)
    frame['label'] = (frame['future_return'] >= 0.02).astype(int)
    return frame


def test_dataset_builder_preserves_metadata_features_and_targets():
    daily = _labeled_frame()

    result = DatasetBuilder().build(daily)

    assert list(result.columns) == list(DATASET_COLUMNS)
    assert len(result) == len(daily)
    pd.testing.assert_frame_equal(result[list(METADATA_COLUMNS)], daily[list(METADATA_COLUMNS)])
    pd.testing.assert_frame_equal(result[list(FEATURE_COLUMNS)], daily[list(FEATURE_COLUMNS)])
    pd.testing.assert_frame_equal(result[list(TARGET_COLUMNS)], daily[list(TARGET_COLUMNS)])


def test_dataset_builder_orders_columns_metadata_features_targets():
    daily = _labeled_frame()

    result = DatasetBuilder().build(daily)

    assert list(result.columns[:2]) == list(METADATA_COLUMNS)
    assert list(result.columns[2:22]) == list(FEATURE_COLUMNS)
    assert list(result.columns[22:]) == list(TARGET_COLUMNS)


def test_dataset_builder_excludes_raw_market_columns():
    daily = _labeled_frame()

    result = DatasetBuilder().build(daily)

    excluded_columns = {
        'open',
        'high',
        'low',
        'close',
        'volume',
        'amount',
        'amplitude',
        'pct_change',
        'change',
        'turnover',
    }
    assert excluded_columns.isdisjoint(set(result.columns))


def test_dataset_builder_exposes_feature_and_target_properties():
    builder = DatasetBuilder()

    assert builder.feature_columns == FEATURE_COLUMNS
    assert builder.target_columns == TARGET_COLUMNS


def test_build_dataset_delegates_to_builder():
    daily = _labeled_frame()

    result = build_dataset(daily)

    assert list(result.columns) == list(DATASET_COLUMNS)


def test_dataset_builder_raises_when_feature_columns_missing():
    daily = _labeled_frame().drop(columns=['macd'])

    with pytest.raises(ValueError, match='missing feature columns'):
        DatasetBuilder().build(daily)


def test_dataset_builder_raises_when_target_columns_missing():
    daily = _labeled_frame().drop(columns=['label'])

    with pytest.raises(ValueError, match='missing target columns'):
        DatasetBuilder().build(daily)
