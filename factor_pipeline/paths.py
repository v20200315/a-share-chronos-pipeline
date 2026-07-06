from __future__ import annotations

import os
from pathlib import Path

FACTOR_OUTPUT_DIR = Path('data/factor_pipeline/output')
MARKET_DATA_SNAPSHOT_LATEST = Path('data/market_data/snapshots/latest')


def validate_output_dir(output_dir: str | Path) -> Path:
    """Create and validate a writable factor output directory.

    Args:
        output_dir: Directory that stores exported factor parquet files.

    Returns:
        Resolved output directory path.

    Raises:
        PermissionError: If the directory exists but is not writable.
    """
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    if not os.access(target, os.W_OK):
        raise PermissionError(f'output directory is not writable: {target}')
    return target
