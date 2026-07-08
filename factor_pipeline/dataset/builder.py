from __future__ import annotations

import logging

import pandas as pd

from factor_pipeline.factors.price import PRICE_FACTOR_COLUMNS
from factor_pipeline.factors.technical import TECHNICAL_FACTOR_COLUMNS
from factor_pipeline.factors.volatility import VOLATILITY_FACTOR_COLUMNS
from factor_pipeline.factors.volume import VOLUME_FACTOR_COLUMNS
from factor_pipeline.labels.label_generator import LABEL_COLUMNS

logger = logging.getLogger(__name__)

METADATA_COLUMNS: tuple[str, ...] = ('date', 'code')
FEATURE_COLUMNS: tuple[str, ...] = (
    *TECHNICAL_FACTOR_COLUMNS,
    *PRICE_FACTOR_COLUMNS,
    *VOLUME_FACTOR_COLUMNS,
    *VOLATILITY_FACTOR_COLUMNS,
)
TARGET_COLUMNS: tuple[str, ...] = LABEL_COLUMNS
DATASET_COLUMNS: tuple[str, ...] = (*METADATA_COLUMNS, *FEATURE_COLUMNS, *TARGET_COLUMNS)


class DatasetBuilder:
    """Organize a labeled factor DataFrame into a research-ready dataset layout."""

    @property
    def feature_columns(self) -> tuple[str, ...]:
        """Return the ordered feature column names used by the dataset builder."""
        return FEATURE_COLUMNS

    @property
    def target_columns(self) -> tuple[str, ...]:
        """Return the ordered target column names used by the dataset builder."""
        return TARGET_COLUMNS

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and reorder metadata, feature, and target columns.

        Args:
            df: Labeled factor DataFrame produced by upstream pipeline stages.

        Returns:
            A new DataFrame containing only metadata, feature, and target columns
            in research-ready order. Row count and values are preserved.

        Raises:
            ValueError: If required feature or target columns are missing.
        """
        _validate_feature_columns(df)
        _validate_target_columns(df)

        result = self._select_columns(df)
        logger.info('feature column count: %s', len(self.feature_columns))
        logger.info('target column count: %s', len(self.target_columns))
        logger.info('dataset shape: %sx%s', result.shape[0], result.shape[1])
        logger.info('dataset successfully built')
        return result

    def _select_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Select and reorder dataset columns without modifying values.

        Args:
            df: Input DataFrame containing metadata, features, and targets.

        Returns:
            A new DataFrame with columns ordered as metadata, features, then targets.
        """
        return df.loc[:, list(DATASET_COLUMNS)].copy()


def build_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Build a research dataset using the default ``DatasetBuilder``.

    Args:
        df: Labeled factor DataFrame.

    Returns:
        A research-ready DataFrame with metadata, features, and targets only.
    """
    return DatasetBuilder().build(df)


def _validate_feature_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in FEATURE_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'dataset builder missing feature columns: {missing_columns}')


def _validate_target_columns(df: pd.DataFrame) -> None:
    missing_columns = [column for column in TARGET_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f'dataset builder missing target columns: {missing_columns}')
