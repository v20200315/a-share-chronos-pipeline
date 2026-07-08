import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import RobustScaler

from factor_pipeline.dataset.builder import FEATURE_COLUMNS
from factor_pipeline.dataset.scaler import FeatureScaler, scale_dataset

FEATURE_SUBSET = ['macd', 'rsi', 'return_1d']
METADATA_COLUMNS = ['date', 'code']
TARGET_COLUMNS = ['future_return', 'label']


def _dataset_frame(rows: int = 6) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    return pd.DataFrame(
        {
            'date': dates,
            'code': '600000',
            'macd': np.arange(rows, dtype=float) + 1.0,
            'rsi': np.arange(rows, dtype=float) + 10.0,
            'return_1d': np.arange(rows, dtype=float) + 20.0,
            'future_return': np.linspace(0.0, 0.05, rows),
            'label': [0, 1, 0, 1, 0, 1][:rows],
        }
    )


def _full_dataset_frame(rows: int = 6) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    data = {
        'date': dates,
        'code': '600000',
        'future_return': np.linspace(0.0, 0.05, rows),
        'label': [0, 1, 0, 1, 0, 1][:rows],
    }
    for index, column in enumerate(FEATURE_COLUMNS):
        data[column] = np.arange(rows, dtype=float) + index + 1.0
    return pd.DataFrame(data)


def test_fit_transform_returns_dataframe_and_scaler():
    daily = _dataset_frame()
    feature_scaler = FeatureScaler()

    result, scaler = feature_scaler.fit_transform(daily, FEATURE_SUBSET)

    assert isinstance(result, pd.DataFrame)
    assert isinstance(scaler, RobustScaler)
    assert scaler is feature_scaler.scaler


def test_transform_returns_dataframe():
    train = _dataset_frame(rows=6)
    inference = _dataset_frame(rows=4)
    feature_scaler = FeatureScaler()
    feature_scaler.fit_transform(train, FEATURE_SUBSET)

    result = feature_scaler.transform(inference, FEATURE_SUBSET)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == len(inference)


def test_fit_transform_preserves_metadata_columns():
    daily = _dataset_frame()

    result, _ = FeatureScaler().fit_transform(daily, FEATURE_SUBSET)

    pd.testing.assert_series_equal(result['date'], daily['date'], check_names=True)
    pd.testing.assert_series_equal(result['code'], daily['code'], check_names=True)


def test_fit_transform_preserves_target_columns():
    daily = _dataset_frame()

    result, _ = FeatureScaler().fit_transform(daily, FEATURE_SUBSET)

    pd.testing.assert_series_equal(
        result['future_return'], daily['future_return'], check_names=True
    )
    pd.testing.assert_series_equal(result['label'], daily['label'], check_names=True)


def test_fit_transform_scales_feature_columns():
    daily = _dataset_frame()
    cleaned = daily.dropna(subset=FEATURE_SUBSET)
    expected = RobustScaler().fit_transform(cleaned.loc[:, FEATURE_SUBSET].to_numpy())

    result, _ = FeatureScaler().fit_transform(daily, FEATURE_SUBSET)

    np.testing.assert_allclose(result.loc[:, FEATURE_SUBSET].to_numpy(), expected)


def test_transform_scales_feature_columns_with_fitted_scaler():
    train = _dataset_frame(rows=6)
    inference = _dataset_frame(rows=4)
    feature_scaler = FeatureScaler()
    feature_scaler.fit_transform(train, FEATURE_SUBSET)
    cleaned = inference.dropna(subset=FEATURE_SUBSET)
    expected = feature_scaler.scaler.transform(cleaned.loc[:, FEATURE_SUBSET].to_numpy())

    result = feature_scaler.transform(inference, FEATURE_SUBSET)

    np.testing.assert_allclose(result.loc[:, FEATURE_SUBSET].to_numpy(), expected)


def test_fit_transform_removes_rows_with_feature_nan_only():
    daily = _dataset_frame(rows=5)
    daily.loc[1, 'macd'] = np.nan
    daily.loc[2, 'future_return'] = np.nan

    result, _ = FeatureScaler().fit_transform(daily, FEATURE_SUBSET)

    assert len(result) == 4
    assert 1 not in result.index
    assert 2 in result.index
    assert pd.isna(result.loc[2, 'future_return'])


def test_fit_transform_preserves_column_order_and_index():
    daily = _dataset_frame(rows=5)
    daily.loc[1, 'macd'] = np.nan

    result, _ = FeatureScaler().fit_transform(daily, FEATURE_SUBSET)

    assert list(result.columns) == list(daily.columns)
    assert list(result.index) == [0, 2, 3, 4]


def test_transform_raises_when_scaler_not_fitted():
    daily = _dataset_frame()

    with pytest.raises(ValueError, match='feature scaler is not fitted'):
        FeatureScaler().transform(daily, FEATURE_SUBSET)


def test_fit_transform_raises_for_invalid_feature_columns():
    daily = _dataset_frame().drop(columns=['macd'])

    with pytest.raises(ValueError, match='missing feature columns'):
        FeatureScaler().fit_transform(daily, FEATURE_SUBSET)


def test_fit_transform_raises_for_empty_feature_columns():
    daily = _dataset_frame()

    with pytest.raises(ValueError, match='at least one feature column'):
        FeatureScaler().fit_transform(daily, [])


def test_fit_transform_raises_for_empty_dataframe():
    daily = pd.DataFrame(columns=['date', 'code', 'macd', 'future_return', 'label'])

    with pytest.raises(ValueError, match='non-empty DataFrame'):
        FeatureScaler().fit_transform(daily, ['macd'])


def test_fit_transform_raises_when_all_rows_removed_by_feature_nan():
    daily = _dataset_frame(rows=2)
    daily['macd'] = np.nan

    with pytest.raises(ValueError, match='no rows remaining'):
        FeatureScaler().fit_transform(daily, FEATURE_SUBSET)


def test_scale_dataset_delegates_to_feature_scaler():
    daily = _full_dataset_frame(rows=6)

    result = scale_dataset(daily)

    assert isinstance(result, pd.DataFrame)
    assert len(result) <= len(daily)
    assert list(result.columns) == list(daily.columns)
    for column in METADATA_COLUMNS + TARGET_COLUMNS:
        pd.testing.assert_series_equal(
            result[column], daily.loc[result.index, column], check_names=True
        )
