from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger(__name__)


class FeatureScaler:
    """Scale factor feature columns with RobustScaler while preserving metadata and targets."""

    def __init__(self) -> None:
        """Initialize an unfitted feature scaler."""
        self.scaler: RobustScaler | None = None

    def fit_transform(
        self,
        df: pd.DataFrame,
        feature_columns: list[str],
    ) -> tuple[pd.DataFrame, RobustScaler]:
        """Fit a RobustScaler on feature columns and return a scaled DataFrame.

        Rows containing NaN in any feature column are removed before fitting.

        Args:
            df: Built factor dataset containing metadata, features, and targets.
            feature_columns: Feature column names to scale.

        Returns:
            A tuple of the scaled DataFrame and the fitted ``RobustScaler``.

        Raises:
            ValueError: If the input is empty, feature columns are invalid, or no rows
                remain after removing feature NaNs.
        """
        _validate_dataframe(df)
        _validate_feature_columns(feature_columns, df)

        logger.info('scaling started')
        original_row_count = len(df)
        cleaned = _drop_feature_nan_rows(df, feature_columns)
        removed_row_count = original_row_count - len(cleaned)
        final_row_count = len(cleaned)

        logger.info('original row count: %s', original_row_count)
        logger.info('rows removed because of NaN: %s', removed_row_count)
        logger.info('final row count: %s', final_row_count)

        if final_row_count == 0:
            raise ValueError('feature scaling has no rows remaining after removing feature NaNs')

        feature_values = cleaned.loc[:, feature_columns].to_numpy()
        self.scaler = RobustScaler()
        scaled_values = self.scaler.fit_transform(feature_values)
        result = _apply_scaled_features(cleaned, feature_columns, scaled_values)

        logger.info('number of features scaled: %s', len(feature_columns))
        logger.info('scaling completed')
        return result, self.scaler

    def transform(
        self,
        df: pd.DataFrame,
        feature_columns: list[str],
    ) -> pd.DataFrame:
        """Transform feature columns using a previously fitted scaler.

        Rows containing NaN in any feature column are removed before transforming.

        Args:
            df: Built factor dataset containing metadata, features, and targets.
            feature_columns: Feature column names to scale.

        Returns:
            A new DataFrame with scaled feature columns only.

        Raises:
            ValueError: If the scaler is not fitted, the input is empty, feature columns
                are invalid, or no rows remain after removing feature NaNs.
        """
        if self.scaler is None:
            raise ValueError('feature scaler is not fitted')

        _validate_dataframe(df)
        _validate_feature_columns(feature_columns, df)

        logger.info('scaling started')
        original_row_count = len(df)
        cleaned = _drop_feature_nan_rows(df, feature_columns)
        removed_row_count = original_row_count - len(cleaned)
        final_row_count = len(cleaned)

        logger.info('original row count: %s', original_row_count)
        logger.info('rows removed because of NaN: %s', removed_row_count)
        logger.info('final row count: %s', final_row_count)

        if final_row_count == 0:
            raise ValueError('feature scaling has no rows remaining after removing feature NaNs')

        feature_values = cleaned.loc[:, feature_columns].to_numpy()
        scaled_values = self.scaler.transform(feature_values)
        result = _apply_scaled_features(cleaned, feature_columns, scaled_values)

        logger.info('number of features scaled: %s', len(feature_columns))
        logger.info('scaling completed')
        return result


def scale_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Scale all builder-defined feature columns using the default ``FeatureScaler``.

    Args:
        df: Built factor dataset from ``build_dataset()``.

    Returns:
        A scaled DataFrame with feature columns transformed by ``RobustScaler``.
    """
    from factor_pipeline.dataset.builder import FEATURE_COLUMNS

    scaled_df, _ = FeatureScaler().fit_transform(df, list(FEATURE_COLUMNS))
    return scaled_df


def _validate_dataframe(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError('feature scaling requires a non-empty DataFrame')


def _validate_feature_columns(feature_columns: list[str], df: pd.DataFrame) -> None:
    if not feature_columns:
        raise ValueError('feature scaling requires at least one feature column')

    missing_columns = [column for column in feature_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f'feature scaling missing feature columns: {missing_columns}')


def _drop_feature_nan_rows(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return df.dropna(subset=feature_columns).copy()


def _apply_scaled_features(
    df: pd.DataFrame,
    feature_columns: list[str],
    scaled_values: np.ndarray,
) -> pd.DataFrame:
    result = df.copy()
    result.loc[:, feature_columns] = scaled_values
    return result
