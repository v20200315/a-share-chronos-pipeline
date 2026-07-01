from __future__ import annotations

from pathlib import Path

DATA_ROOT = Path('data')
MARKET_DATA_ROOT = DATA_ROOT / 'market_data'
FEATURES_ROOT = DATA_ROOT / 'features'

MARKET_DATA_METADATA_ROOT = MARKET_DATA_ROOT / 'metadata'
MARKET_DATA_DAILY_BARS_ROOT = MARKET_DATA_ROOT / 'daily_bars'
MARKET_DATA_SNAPSHOTS_ROOT = MARKET_DATA_ROOT / 'snapshots'
MARKET_DATA_AUDIT_ROOT = MARKET_DATA_ROOT / 'audit'

DEFAULT_DAILY_PROVIDER = 'akshare'
DEFAULT_DAILY_ADJUST = 'qfq'
DEFAULT_DAILY_FREQUENCY = '1d'


def metadata_provider_dir(provider_name: str) -> Path:
    return MARKET_DATA_METADATA_ROOT / f'provider={provider_name}'


def metadata_file_path(provider_name: str) -> Path:
    return metadata_provider_dir(provider_name) / 'stock_basic.parquet'


def metadata_audit_dir(provider_name: str) -> Path:
    return MARKET_DATA_AUDIT_ROOT / 'metadata' / f'provider={provider_name}'


def daily_bars_dir(
    *,
    provider_name: str = DEFAULT_DAILY_PROVIDER,
    adjust: str = DEFAULT_DAILY_ADJUST,
    frequency: str = DEFAULT_DAILY_FREQUENCY,
) -> Path:
    return (
        MARKET_DATA_DAILY_BARS_ROOT
        / f'provider={provider_name}'
        / f'adjust={adjust}'
        / f'frequency={frequency}'
    )


def daily_bars_audit_dir(provider_name: str = DEFAULT_DAILY_PROVIDER) -> Path:
    return MARKET_DATA_AUDIT_ROOT / 'daily_bars' / f'provider={provider_name}'


def snapshot_dir(snapshot_name: str = 'latest') -> Path:
    return MARKET_DATA_SNAPSHOTS_ROOT / snapshot_name
