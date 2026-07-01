import json
from pathlib import Path

import pandas as pd

from market_data_pipeline.daily.manager import DailyBarManager
from market_data_pipeline.metadata.manager import MetadataManager
from market_data_pipeline.snapshot import MarketDataSnapshotPublisher


class FakeMetadataProvider:
    provider_name = 'fake'

    def fetch_stock_basic(self):
        return pd.DataFrame()


def test_market_data_managers_use_pipeline_owned_default_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    metadata_manager = MetadataManager(provider=FakeMetadataProvider())
    daily_manager = DailyBarManager(show_progress=False)

    assert metadata_manager.file_path == Path(
        'data/market_data/metadata/provider=fake/stock_basic.parquet'
    )
    assert metadata_manager.audit_dir == Path('data/market_data/audit/metadata/provider=fake')
    assert daily_manager.data_dir == Path(
        'data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d'
    )
    assert daily_manager.metadata_path == Path(
        'data/market_data/metadata/provider=akshare/stock_basic.parquet'
    )
    assert daily_manager.audit_dir == Path('data/market_data/audit/daily_bars/provider=akshare')


def test_snapshot_publisher_writes_feature_input_contract(tmp_path):
    metadata_path = tmp_path / 'metadata' / 'stock_basic.parquet'
    daily_dir = tmp_path / 'daily_bars'
    snapshots_root = tmp_path / 'snapshots'
    metadata_path.parent.mkdir(parents=True)
    daily_dir.mkdir()

    pd.DataFrame(
        [
            {
                'code': '600519',
                'name': '贵州茅台',
                'exchange': 'SH',
                'list_date': '2001-08-27',
            },
            {
                'code': '000001',
                'name': '平安银行',
                'exchange': 'SZ',
                'list_date': '1991-04-03',
            },
        ]
    ).to_parquet(metadata_path, index=False)
    pd.DataFrame(
        [
            {'code': '600519', 'date': '2021-06-16', 'close': 1.0},
            {'code': '600519', 'date': '2026-06-16', 'close': 2.0},
        ]
    ).to_parquet(daily_dir / '600519.parquet', index=False)
    pd.DataFrame(
        [
            {'code': '000001', 'date': '2022-01-01', 'close': 1.0},
            {'code': '000001', 'date': '2026-06-15', 'close': 2.0},
        ]
    ).to_parquet(daily_dir / '000001.parquet', index=False)

    publisher = MarketDataSnapshotPublisher(
        metadata_path=metadata_path,
        daily_dir=daily_dir,
        snapshots_root=snapshots_root,
    )
    result = publisher.publish(snapshot_name='2026-07-01T135635')

    snapshot_dir = snapshots_root / '2026-07-01T135635'
    latest_dir = snapshots_root / 'latest'
    assert result.snapshot_dir == snapshot_dir
    assert result.manifest_path == snapshot_dir / 'manifest.json'
    assert result.latest_dir == latest_dir
    assert (snapshot_dir / 'stock_basic.parquet').exists()
    assert (snapshot_dir / 'daily_bars' / '000001.parquet').exists()
    assert (latest_dir / 'manifest.json').exists()

    manifest = json.loads(result.manifest_path.read_text(encoding='utf-8'))
    assert manifest['metadata_provider'] == 'akshare'
    assert manifest['daily_bars_provider'] == 'akshare'
    assert manifest['adjust'] == 'qfq'
    assert manifest['frequency'] == '1d'
    assert manifest['metadata_path'] == str(snapshot_dir / 'stock_basic.parquet')
    assert manifest['daily_bars_path'] == str(snapshot_dir / 'daily_bars')
    assert manifest['symbol_count'] == 2
    assert manifest['symbols'] == ['000001', '600519']
    assert manifest['date_coverage'] == {
        'start_date': '2021-06-16',
        'end_date': '2026-06-16',
    }
