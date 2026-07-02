from __future__ import annotations

from pathlib import Path

MARKET_DATA_SNAPSHOT_LATEST = Path('data/market_data/snapshots/latest')
FEATURES_ROOT = Path('data/features')

FEATURE_SET_NAME = 'technical_indicators'
FEATURE_VERSION = 'v1'


def feature_output_dir(
    *,
    feature_set: str = FEATURE_SET_NAME,
    version: str = FEATURE_VERSION,
) -> Path:
    return FEATURES_ROOT / feature_set / f'version={version}'
