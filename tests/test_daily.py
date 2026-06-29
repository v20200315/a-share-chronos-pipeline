import json
import time
from datetime import date

import pandas as pd
import pytest

from chronos_pipeline.daily.akshare_provider import AkshareDailyBarProvider
from chronos_pipeline.daily.manager import DailyBarManager


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
                },
                {
                    'code': code,
                    'date': end_date.strftime('%Y-%m-%d'),
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
                },
            ]
        )


class TrackingDailyBarProvider(FakeDailyBarProvider):
    def __init__(self, *, sleep_seconds: float = 0.01):
        super().__init__()
        self.active_calls = 0
        self.max_active_calls = 0
        self.sleep_seconds = sleep_seconds

    def fetch_daily_bars(self, code, start_date, end_date):
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            time.sleep(self.sleep_seconds)
            return super().fetch_daily_bars(code, start_date, end_date)
        finally:
            self.active_calls -= 1


class FailingDailyBarProvider(FakeDailyBarProvider):
    def __init__(self, failed_code: str):
        super().__init__()
        self.failed_code = failed_code

    def fetch_daily_bars(self, code, start_date, end_date):
        if code == self.failed_code:
            raise RuntimeError('boom')
        return super().fetch_daily_bars(code, start_date, end_date)


class IncompleteDailyBarProvider(FakeDailyBarProvider):
    def __init__(self, mode: str):
        super().__init__()
        self.mode = mode

    def fetch_daily_bars(self, code, start_date, end_date):
        self.calls.append((code, start_date, end_date))
        if self.mode == 'empty':
            return pd.DataFrame(columns=['code', 'date'])
        if self.mode == 'missing_date':
            return pd.DataFrame([{'code': code, 'close': 1.0}])
        if self.mode == 'invalid_date':
            return pd.DataFrame([{'code': code, 'date': 'bad-date'}])
        if self.mode == 'late_start':
            return pd.DataFrame(
                [
                    {'code': code, 'date': '2021-06-24'},
                    {'code': code, 'date': end_date.strftime('%Y-%m-%d')},
                ]
            )
        if self.mode == 'early_end':
            return pd.DataFrame(
                [
                    {'code': code, 'date': start_date.strftime('%Y-%m-%d')},
                    {'code': code, 'date': '2026-06-08'},
                ]
            )

        raise ValueError(f'unsupported incomplete mode: {self.mode}')


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


def _write_metadata(metadata_dir):
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
            {
                'code': '300750',
                'name': '宁德时代',
                'exchange': 'SZ',
                'list_date': '2018-06-11',
            },
        ]
    ).to_parquet(metadata_dir / 'stock_basic_akshare.parquet', index=False)


def test_daily_bar_manager_writes_one_parquet_per_symbol(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

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


def test_daily_bar_manager_refresh_top_limits_sorted_metadata(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

    provider = FakeDailyBarProvider()
    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=provider,
        today=date(2026, 6, 16),
        show_progress=False,
    )

    report = manager.refresh(top=2)

    assert [path.name for path in report.saved_paths] == ['000001.parquet', '300750.parquet']
    assert sorted(call[0] for call in provider.calls) == ['000001', '300750']
    assert not (daily_dir / '600519.parquet').exists()


def test_daily_bar_manager_refresh_rejects_invalid_top(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=FakeDailyBarProvider(),
        today=date(2026, 6, 16),
        show_progress=False,
    )

    with pytest.raises(ValueError, match='top must be a positive integer'):
        manager.refresh(top=0)


def test_daily_bar_manager_refresh_limits_max_concurrency(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

    provider = TrackingDailyBarProvider()
    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=provider,
        today=date(2026, 6, 16),
        show_progress=False,
    )

    report = manager.refresh(max_concurrency=2)

    assert len(report.saved_paths) == 3
    assert provider.max_active_calls <= 2


def test_daily_bar_manager_refresh_continues_after_symbol_failure(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

    provider = FailingDailyBarProvider(failed_code='300750')
    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=provider,
        today=date(2026, 6, 16),
        show_progress=False,
    )

    report = manager.refresh(max_concurrency=2)

    assert report.failed_codes == ['300750']
    assert [path.name for path in report.saved_paths] == ['000001.parquet', '600519.parquet']
    assert (daily_dir / '000001.parquet').exists()
    assert (daily_dir / '600519.parquet').exists()
    assert not (daily_dir / '300750.parquet').exists()


def test_daily_bar_manager_writes_local_report(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

    provider = FailingDailyBarProvider(failed_code='300750')
    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=provider,
        today=date(2026, 6, 16),
        show_progress=False,
    )

    report = manager.refresh(symbols=['600519', '300750'])

    assert report.report_path is not None
    assert report.report_path.exists()
    assert report.report_path.parent == daily_dir / 'audit'

    payload = json.loads(report.report_path.read_text(encoding='utf-8'))
    assert payload['saved_count'] == 1
    assert payload['skipped_count'] == 0
    assert payload['failed_count'] == 1
    assert payload['failed_codes'] == ['300750']
    assert payload['failed_reasons'] == {'300750': 'boom'}
    assert 'saved_paths' not in payload
    assert payload['report_path'] == str(report.report_path)


@pytest.mark.parametrize(
    'mode',
    ['empty', 'missing_date', 'invalid_date', 'late_start', 'early_end'],
)
def test_daily_bar_manager_refresh_fails_incomplete_data_without_writing(tmp_path, mode):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=IncompleteDailyBarProvider(mode),
        today=date(2026, 6, 16),
        show_progress=False,
    )

    report = manager.refresh(symbols=['600519'])

    assert report.saved_paths == []
    assert report.failed_codes == ['600519']
    assert not (daily_dir / '600519.parquet').exists()


def test_daily_bar_manager_refresh_rejects_invalid_max_concurrency(tmp_path):
    metadata_dir = tmp_path / 'metadata'
    daily_dir = tmp_path / 'daily'
    _write_metadata(metadata_dir)

    manager = DailyBarManager(
        data_dir=daily_dir,
        metadata_dir=metadata_dir,
        provider=FakeDailyBarProvider(),
        today=date(2026, 6, 16),
        show_progress=False,
    )

    with pytest.raises(ValueError, match='max_concurrency must be a positive integer'):
        manager.refresh(max_concurrency=0)
