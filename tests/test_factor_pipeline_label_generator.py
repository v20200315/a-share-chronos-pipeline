import numpy as np
import pandas as pd
import pytest

from factor_pipeline.labels.label_generator import (
    LABEL_COLUMNS,
    LabelGenerator,
    generate_labels,
)
from factor_pipeline.io.loader import REQUIRED_COLUMNS


def _factor_frame(rows: int = 20) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 12.0, rows)
    return pd.DataFrame(
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


def test_label_generator_appends_future_return_and_label():
    daily = _factor_frame(rows=20)
    original_columns = list(daily.columns)

    result = LabelGenerator(horizon=5, threshold=0.02).generate(daily)

    assert list(result.columns) == [*original_columns, *LABEL_COLUMNS]
    assert set(result['label'].unique()).issubset({0, 1})

    expected_future_return = daily['close'].shift(-5) / daily['close'] - 1
    pd.testing.assert_series_equal(
        result['future_return'],
        expected_future_return.iloc[:-5],
        check_names=False,
    )
    expected_labels = (expected_future_return >= 0.02).astype(int)
    pd.testing.assert_series_equal(
        result['label'],
        expected_labels.iloc[:-5],
        check_names=False,
    )


def test_label_generator_removes_tail_rows_for_default_horizon():
    daily = _factor_frame(rows=20)

    result = LabelGenerator().generate(daily)

    assert len(result) == len(daily) - 5


def test_label_generator_supports_configurable_horizon():
    daily = _factor_frame(rows=15)

    result = LabelGenerator(horizon=3).generate(daily)

    assert len(result) == len(daily) - 3


def test_label_generator_supports_configurable_threshold():
    daily = pd.DataFrame(
        {
            'code': '600000',
            'date': pd.date_range('2024-01-01', periods=3, freq='D'),
            'open': [10.0, 10.0, 10.0],
            'high': [10.5, 10.5, 10.5],
            'low': [9.5, 9.5, 9.5],
            'close': [10.0, 10.2, 10.0],
            'volume': [1000, 1000, 1000],
            'amount': [10000.0, 10200.0, 10000.0],
            'amplitude': [1.0, 1.0, 1.0],
            'pct_change': [0.0, 0.02, -0.0196],
            'change': [0.0, 0.2, -0.2],
            'turnover': [0.5, 0.5, 0.5],
        },
        columns=list(REQUIRED_COLUMNS),
    )

    positive = LabelGenerator(horizon=1, threshold=0.02).generate(daily)
    negative = LabelGenerator(horizon=1, threshold=0.03).generate(daily)

    assert positive['label'].iloc[0] == 1
    assert negative['label'].iloc[0] == 0


def test_generate_labels_delegates_to_generator():
    daily = _factor_frame(rows=12)

    result = generate_labels(daily)

    assert list(result.columns) == [*daily.columns, *LABEL_COLUMNS]
    assert len(result) == len(daily) - 5


def test_label_generator_raises_when_close_missing():
    daily = _factor_frame().drop(columns=['close'])

    with pytest.raises(ValueError, match='missing required columns'):
        LabelGenerator().generate(daily)


def test_label_generator_raises_when_columns_already_exist():
    daily = _factor_frame()
    daily['label'] = 0

    with pytest.raises(ValueError, match='would overwrite existing columns'):
        LabelGenerator().generate(daily)
