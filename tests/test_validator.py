import pandas as pd
import pytest

from chronos_pipeline.metadata.eastmoney_provider import EastMoneyMetadataProvider
from chronos_pipeline.metadata.exchange import infer_exchange
from chronos_pipeline.metadata.validator import (
    MetadataValidationError,
    MetadataValidator,
)


def _sample_df(**overrides) -> pd.DataFrame:
    rows = [
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
        {
            'code': '920001',
            'name': '示例北交所',
            'exchange': 'BJ',
            'list_date': '2024-01-01',
        },
    ]
    df = pd.DataFrame(rows)
    for key, value in overrides.items():
        df[key] = value
    return df


def test_infer_exchange():
    assert infer_exchange('600519') == 'SH'
    assert infer_exchange('688001') == 'SH'
    assert infer_exchange('000001') == 'SZ'
    assert infer_exchange('300750') == 'SZ'
    assert infer_exchange('920001') == 'BJ'


def test_eastmoney_parses_jsonp_response():
    payload = (
        'jQuery37106414938370754382_1781081311474({'
        '"rc":0,"data":{"total":1,"diff":[{"f12":"603103","f14":"横店影视","f26":20171012}]}'
        '});'
    )

    parsed = EastMoneyMetadataProvider._parse_jsonp(payload)

    assert parsed['data']['total'] == 1
    assert parsed['data']['diff'][0]['f12'] == '603103'


def test_eastmoney_normalizes_rows_to_stock_basic_schema():
    df = EastMoneyMetadataProvider._normalize_rows(
        [
            {'f12': '603103', 'f14': '横店影视', 'f26': 20171012},
            {'f12': '002181', 'f14': '粤 传 媒', 'f26': 20071116},
        ]
    )

    assert list(df.columns) == ['code', 'name', 'exchange', 'list_date']
    assert df.loc[0].to_dict() == {
        'code': '603103',
        'name': '横店影视',
        'exchange': 'SH',
        'list_date': '2017-10-12',
    }
    assert df.loc[1].to_dict() == {
        'code': '002181',
        'name': '粤 传 媒',
        'exchange': 'SZ',
        'list_date': '2007-11-16',
    }


def test_eastmoney_uses_page_size_100_and_56_pages_for_5531_records():
    provider = EastMoneyMetadataProvider()
    params = provider._build_params(page=56)

    assert provider.page_size == 100
    assert params['pz'] == 100
    assert params['pn'] == 56
    assert params['fid'] == 'f12'
    assert EastMoneyMetadataProvider._page_count(total=5531, page_size=100) == 56


def test_eastmoney_fetch_all_rows_uses_first_page_total_for_page_count(monkeypatch):
    requested_pages = []

    def fake_fetch_page(self, client, page):
        requested_pages.append(page)
        return {
            'data': {
                'total': 250,
                'diff': [{'f12': f'{page:06d}', 'f14': f'name-{page}', 'f26': 20200101}],
            }
        }

    monkeypatch.setattr(EastMoneyMetadataProvider, '_fetch_page', fake_fetch_page)

    provider = EastMoneyMetadataProvider(page_size=100, show_progress=False)
    rows = provider._fetch_all_rows()

    assert requested_pages == [1, 2, 3]
    assert len(rows) == 3


def test_validate_structure_passes_with_relaxed_bounds(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    report = MetadataValidator.validate_stock_basic(_sample_df())

    assert report.passed
    assert not report.errors


def test_validate_structure_detects_duplicate_code(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    df = pd.concat([_sample_df(), _sample_df().iloc[[0]]], ignore_index=True)
    report = MetadataValidator.validate_stock_basic(df)

    assert not report.passed
    assert any('duplicate code' in issue.message for issue in report.errors)


def test_validate_missing_required_columns_does_not_crash_with_diff(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    df = pd.DataFrame([{'name': 'missing-code'}])
    previous_df = _sample_df()

    report = MetadataValidator.validate_stock_basic(
        df,
        previous_df=previous_df,
    )

    assert not report.passed
    assert any('missing required columns' in issue.message for issue in report.errors)
    assert any('skip snapshot diff' in issue.message for issue in report.warnings)


def test_validate_diff_skips_when_current_or_previous_codes_are_not_unique(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    current_df = pd.concat([_sample_df(), _sample_df().iloc[[0]]], ignore_index=True)
    previous_df = _sample_df()

    report = MetadataValidator.validate_stock_basic(current_df, previous_df=previous_df)

    assert not report.passed
    assert report.diff is None
    assert any('skip snapshot diff because code is not unique' in issue.message for issue in report.warnings)


def test_validate_diff_skips_when_previous_snapshot_codes_are_not_unique(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    current_df = _sample_df()
    previous_df = pd.concat([_sample_df(), _sample_df().iloc[[0]]], ignore_index=True)

    report = MetadataValidator.validate_stock_basic(current_df, previous_df=previous_df)

    assert report.passed
    assert report.diff is None
    assert any('skip snapshot diff because code is not unique' in issue.message for issue in report.warnings)


def test_validate_diff_flags_large_removal(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)
    monkeypatch.setattr(MetadataValidator, 'MAX_REMOVED_RATIO', 0.01)

    previous_df = _sample_df()
    current_df = previous_df.iloc[[0]].copy()

    report = MetadataValidator.validate_stock_basic(current_df, previous_df=previous_df)

    assert not report.passed
    assert report.diff is not None
    assert report.diff.removed_codes == ['000001', '920001']


def test_strict_promotes_warnings_to_errors(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)
    monkeypatch.setattr(MetadataValidator, 'MAX_UNKNOWN_RATIO', 0.0)

    df = _sample_df()
    df.loc[df['code'] == '920001', 'list_date'] = pd.NA

    report = MetadataValidator.validate_stock_basic(df, strict=True)

    assert not report.passed
    assert any('[strict]' in issue.message for issue in report.errors)


def test_clean_stock_basic_removes_errors_but_keeps_warning_rows_without_strict():
    df = _sample_df()
    missing_list_date = pd.DataFrame(
        [
            {
                'code': '300750',
                'name': '宁德时代',
                'exchange': 'SZ',
                'list_date': pd.NA,
            }
        ]
    )
    df = pd.concat([df, df.iloc[[0]], missing_list_date], ignore_index=True)
    df.loc[1, 'list_date'] = '2099-01-01'
    df.loc[2, 'exchange'] = 'SH'

    cleaned, report = MetadataValidator.clean_stock_basic(df)

    assert report.row_count_before == 5
    assert report.row_count_after == 2
    assert report.removed_count == 3
    assert cleaned['code'].tolist() == ['600519', '300750']


def test_clean_stock_basic_removes_warning_rows_with_strict():
    df = _sample_df()
    df.loc[0, 'list_date'] = pd.NA

    cleaned, report = MetadataValidator.clean_stock_basic(df, strict=True)

    assert report.row_count_before == 3
    assert report.row_count_after == 2
    assert report.removed_count == 1
    assert '600519' not in set(cleaned['code'])


def test_manager_refresh_preserves_fetched_rows_without_validation(tmp_path, monkeypatch):
    from chronos_pipeline.metadata.manager import MetadataManager

    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    data_dir = tmp_path / 'metadata'
    data_dir.mkdir()
    parquet_path = data_dir / 'stock_basic_akshare.parquet'
    previous_df = _sample_df()
    previous_df.to_parquet(parquet_path, index=False)

    manager = MetadataManager(data_dir=data_dir)

    class BrokenProvider:
        provider_name = 'akshare'

        def fetch_stock_basic(self):
            return pd.concat([previous_df.iloc[[0]], previous_df.iloc[[0]]], ignore_index=True)

    manager.provider = BrokenProvider()

    df = manager.refresh()

    reloaded = pd.read_parquet(parquet_path)
    assert len(df) == 2
    assert len(reloaded) == 2


def test_manager_clean_removes_errors_from_parquet(tmp_path, monkeypatch):
    from chronos_pipeline.metadata.manager import MetadataManager

    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    data_dir = tmp_path / 'metadata'
    data_dir.mkdir()
    parquet_path = data_dir / 'stock_basic_akshare.parquet'
    df = _sample_df()
    df.loc[0, 'list_date'] = '2099-01-01'
    df.to_parquet(parquet_path, index=False)

    manager = MetadataManager(data_dir=data_dir)
    cleaned, report = manager.clean()

    reloaded = pd.read_parquet(parquet_path)
    assert report.removed_count == 1
    assert len(cleaned) == 2
    assert len(reloaded) == 2
    assert '600519' not in set(reloaded['code'])


def test_manager_clean_strict_removes_warning_rows_from_parquet(tmp_path, monkeypatch):
    from chronos_pipeline.metadata.manager import MetadataManager

    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    data_dir = tmp_path / 'metadata'
    data_dir.mkdir()
    parquet_path = data_dir / 'stock_basic_akshare.parquet'
    df = _sample_df()
    df.loc[0, 'list_date'] = pd.NA
    df.to_parquet(parquet_path, index=False)

    manager = MetadataManager(data_dir=data_dir)
    cleaned, report = manager.clean(strict=True)

    reloaded = pd.read_parquet(parquet_path)
    assert report.removed_count == 1
    assert len(cleaned) == 2
    assert len(reloaded) == 2
    assert '600519' not in set(reloaded['code'])


def test_manager_clean_dry_run_does_not_modify_parquet(tmp_path, monkeypatch):
    from chronos_pipeline.metadata.manager import MetadataManager

    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    data_dir = tmp_path / 'metadata'
    data_dir.mkdir()
    parquet_path = data_dir / 'stock_basic_akshare.parquet'
    df = _sample_df()
    df.loc[0, 'list_date'] = '2099-01-01'
    df.to_parquet(parquet_path, index=False)

    manager = MetadataManager(data_dir=data_dir)
    cleaned, report = manager.clean(dry_run=True)

    reloaded = pd.read_parquet(parquet_path)
    assert report.removed_count == 1
    assert len(cleaned) == 2
    assert len(reloaded) == 3


def test_manager_validate_fail_closed(tmp_path, monkeypatch):
    from chronos_pipeline.metadata.manager import MetadataManager

    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    data_dir = tmp_path / 'metadata'
    data_dir.mkdir()
    parquet_path = data_dir / 'stock_basic_akshare.parquet'
    previous_df = _sample_df()
    previous_df.to_parquet(parquet_path, index=False)

    manager = MetadataManager(data_dir=data_dir)
    broken = previous_df.iloc[[0]].copy()
    broken.to_parquet(parquet_path, index=False)

    with pytest.raises(MetadataValidationError):
        manager.validate()

    reloaded = pd.read_parquet(parquet_path)
    assert len(reloaded) == len(broken)
