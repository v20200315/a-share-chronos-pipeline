import pandas as pd
import pytest

from ashare.metadata.exchange import infer_exchange
from ashare.metadata.validator import CrossCheckRefs, MetadataValidationError, MetadataValidator


def _sample_df(**overrides) -> pd.DataFrame:
    rows = [
        {
            'code': '600519',
            'name': '贵州茅台',
            'exchange': 'SH',
            'status': 'LISTED',
            'list_date': '2001-08-27',
            'delist_date': pd.NA,
        },
        {
            'code': '000001',
            'name': '平安银行',
            'exchange': 'SZ',
            'status': 'LISTED',
            'list_date': '1991-04-03',
            'delist_date': pd.NA,
        },
        {
            'code': '920001',
            'name': '示例北交所',
            'exchange': 'BJ',
            'status': 'LISTED',
            'list_date': '2024-01-01',
            'delist_date': pd.NA,
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


def test_validate_cross_check_detects_missing_universe_code(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    df = _sample_df()
    cross_check = CrossCheckRefs(
        universe_codes={'600519', '000001', '920001', '999999'},
        listed_codes={'600519', '000001', '920001'},
    )

    report = MetadataValidator.validate_stock_basic(df, cross_check=cross_check)

    assert not report.passed
    assert any('missing from output' in issue.message for issue in report.errors)


def test_strict_promotes_warnings_to_errors(monkeypatch):
    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)
    monkeypatch.setattr(MetadataValidator, 'MAX_UNKNOWN_RATIO', 0.0)

    df = _sample_df()
    df.loc[df['code'] == '920001', 'status'] = 'UNKNOWN'
    df.loc[df['code'] == '920001', 'list_date'] = pd.NA

    report = MetadataValidator.validate_stock_basic(df, strict=True)

    assert not report.passed
    assert any('[strict]' in issue.message for issue in report.errors)


def test_manager_refresh_fail_closed(tmp_path, monkeypatch):
    from ashare.metadata.manager import MetadataManager

    monkeypatch.setattr(MetadataValidator, 'MIN_ROWS', 1)
    monkeypatch.setattr(MetadataValidator, 'MAX_ROWS', 10)

    data_dir = tmp_path / 'metadata'
    parquet_path = data_dir / 'stock_basic.parquet'
    previous_df = _sample_df()
    previous_df.to_parquet(parquet_path, index=False)

    manager = MetadataManager(data_dir=data_dir)

    class BrokenProvider:
        last_cross_check = CrossCheckRefs(
            universe_codes=set(previous_df['code'].astype(str)),
            listed_codes=set(previous_df['code'].astype(str)),
        )

        def fetch_stock_basic(self):
            broken = previous_df.copy()
            broken.loc[broken['code'] == '000001', 'code'] = '000001'
            return broken.iloc[[0]]

    manager.provider = BrokenProvider()

    with pytest.raises(MetadataValidationError):
        manager.refresh()

    reloaded = pd.read_parquet(parquet_path)
    assert len(reloaded) == len(previous_df)
