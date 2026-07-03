from __future__ import annotations

import pandas as pd


def generate_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Placeholder label generator that adds a temporary label column.

    Args:
        df: Factor-enriched market-data DataFrame.

    Returns:
        A copy of the input DataFrame with ``label = 0`` for every row.
    """
    result = df.copy()
    result['label'] = 0
    return result
