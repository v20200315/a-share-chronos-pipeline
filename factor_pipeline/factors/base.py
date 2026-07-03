from __future__ import annotations

import pandas as pd


def pass_through(df: pd.DataFrame) -> pd.DataFrame:
    """Return the input DataFrame unchanged.

    Args:
        df: Input DataFrame for a factor stage.

    Returns:
        The same DataFrame without modification.
    """
    return df
