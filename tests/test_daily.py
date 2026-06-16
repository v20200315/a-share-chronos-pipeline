from datetime import date

import pandas as pd

from chronos_pipeline.daily.akshare_provider import AkshareDailyBarProvider
from chronos_pipeline.daily.manager import DailyBarManager


def test_calculate_start_date_uses_five_year_window_for_old_listing():
    start_date = DailyBarManager.calculate_start_date(
        '2001-08-27',
        today=date(2026, 6, 16),
    )

    assert start_date == date(2021, 6, 16)


def test_calculate_start_date_uses_list_date_for_recent_listing():
    start_date = DailyBarManager.calculate_start_date(
        '2024-01-01',
        today=date(2026, 6, 16),
    )

    assert start_date == date(2024, 1, 1)


def test_calculate_start_date_returns_none_for_invalid_listing_date():
    assert DailyBarManager.calculate_start_date(None, today=date(2026, 6, 16)) is None
    assert DailyBarManager.calculate_start_date('bad-date', today=date(2026, 6, 16)) is None


def test_akshare_daily_bar_normalize_to_daily_bar_schema():
    raw = pd.DataFrame(
        [
            {
                '日期': '2024-01-02',
                '开盘': '10.1',
                '最高': '10.5',
                '最低': '10.0',
                '收盘': '10.3',
                '成交量': '1000',
                '成交额': '10300',
                '振幅': '5.0',
                '涨跌幅': '1.2',
                '涨跌额': '0.12',
                '换手率': '0.8',
            }
        ]
    )

    df = AkshareDailyBarProvider._normalize(raw, code='600519')

    assert list(df.columns) == AkshareDailyBarProvider.OUTPUT_COLUMNS
    assert df.loc[0].to_dict() == {
        'code': '600519',
        'date': '2024-01-02',
        'open': 10.1,
        'high': 10.5,
        'low': 10.0,
        'close': 10.3,
        'volume': 1000,
        'amount': 10300,
        'amplitude': 5.0,
        'pct_change': 1.2,
        'change': 0.12,
        'turnover': 0.8,
    }


def test_daily_bar_manager_writes_one_parquet_per_symbol(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    metadata_dir.mkdir()
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
                'list_date': '2024-01-01',
            },
        ]
    ).to_parquet(metadata_dir / 'stock_basic_akshare.parquet', index=False)

    class FakeDailyBarProvider:
        provider_name = 'fake'

        def __init__(self):
            self.calls = []

        def fetch_daily_bars(self, code, start_date, end_date):
            self.calls.append((code, start_date, end_date))
            return pd.DataFrame(
                [
                    {
                        'code': code,
                        'date': start_date.strftime('%Y-%m-%d'),
                        'open': 1.0,
                        'high': 1.0,
                        'low': 1.0,
                        'close': 1.0,
                        'volume': 1.0,
                        'amount': 1.0,
                        'amplitude': 0.0,
                        'pct_change': 0.0,
                        'change': 0.0,
                        'turnover': 0.0,
                    }
                ]
            )

    provider = FakeDailyBarProvider()
    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=provider,
        today=date(2026, 6, 16),
        show_progress=False,
    )

    report = manager.refresh(symbols=['600519'])

    output_path = daily_dir / '600519.parquet'
    assert report.saved_paths == [output_path]
    assert output_path.exists()
    assert provider.calls == [('600519', date(2021, 6, 16), date(2026, 6, 16))]

    saved = pd.read_parquet(output_path)
    assert saved.loc[0, 'code'] == '600519'
    assert not (daily_dir / '000001.parquet').exists()
