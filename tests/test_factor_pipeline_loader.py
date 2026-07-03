import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factor_pipeline.engine import FactorEngine
from factor_pipeline.io.exporter import export_factor_dataset
from factor_pipeline.io.loader import (
    REQUIRED_COLUMNS,
    load_market_data,
    load_snapshot,
    validate_required_columns,
)


def _market_data_frame(code: str, rows: int = 5, *, reverse: bool = False) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 15.0, rows)
    df = pd.DataFrame(
        {
            'code': code,
            'date': dates.strftime('%Y-%m-%d'),
            'open': close - 0.1,
            'high': close + 0.5,
            'low': close - 0.5,
            'close': close,
            'volume': np.arange(rows) + 1000,
            'amount': close * (np.arange(rows) + 1000),
            'amplitude': 1.0,
            'pct_change': 0.01,
            'change': 0.1,
            'turnover': 0.5,
        }
    )
    if reverse:
        return df.iloc[::-1].reset_index(drop=True)
    return df


def _write_snapshot(tmp_path: Path) -> Path:
    snapshot_dir = tmp_path / 'snapshot'
    daily_bars_dir = snapshot_dir / 'daily_bars'
    daily_bars_dir.mkdir(parents=True)
    _market_data_frame('000001', reverse=True).to_parquet(
        daily_bars_dir / '000001.parquet',
        index=False,
    )
    _market_data_frame('600000').to_parquet(daily_bars_dir / '600000.parquet', index=False)
    manifest = {
        'daily_bars_path': str(daily_bars_dir),
        'symbols': ['000001', '600000'],
        'metadata_provider': 'akshare',
    }
    (snapshot_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return snapshot_dir


def test_load_snapshot_reads_manifest_and_resolves_daily_bars_dir(tmp_path):
    snapshot_dir = _write_snapshot(tmp_path)

    snapshot = load_snapshot(snapshot_dir)

    assert snapshot.snapshot_dir == snapshot_dir
    assert snapshot.daily_bars_dir == snapshot_dir / 'daily_bars'
    assert snapshot.manifest['symbols'] == ['000001', '600000']


def test_load_market_data_reads_snapshot_without_transforming_rows(tmp_path):
    snapshot_dir = _write_snapshot(tmp_path)
    snapshot = load_snapshot(snapshot_dir)
    expected = pd.read_parquet(snapshot_dir / 'daily_bars' / '000001.parquet')

    loaded = load_market_data('000001', snapshot=snapshot)

    pd.testing.assert_frame_equal(loaded, expected)


def test_load_market_data_normalizes_symbol_to_six_digits(tmp_path):
    snapshot_dir = _write_snapshot(tmp_path)
    snapshot = load_snapshot(snapshot_dir)
    expected = pd.read_parquet(snapshot_dir / 'daily_bars' / '000001.parquet')

    loaded = load_market_data('1', snapshot=snapshot)

    pd.testing.assert_frame_equal(loaded, expected)


def test_load_market_data_uses_daily_bars_dir_override_without_manifest(tmp_path):
    daily_bars_dir = tmp_path / 'daily_bars'
    daily_bars_dir.mkdir(parents=True)
    expected = _market_data_frame('600000')
    expected.to_parquet(daily_bars_dir / '600000.parquet', index=False)

    loaded = load_market_data('600000', daily_bars_dir=daily_bars_dir)

    pd.testing.assert_frame_equal(loaded, expected)


def test_load_snapshot_raises_when_manifest_missing(tmp_path):
    snapshot_dir = tmp_path / 'snapshot'
    snapshot_dir.mkdir()

    with pytest.raises(FileNotFoundError, match='manifest not found'):
        load_snapshot(snapshot_dir)


def test_load_market_data_raises_when_parquet_missing(tmp_path):
    snapshot_dir = _write_snapshot(tmp_path)
    snapshot = load_snapshot(snapshot_dir)

    with pytest.raises(FileNotFoundError, match='market data parquet not found'):
        load_market_data('999999', snapshot=snapshot)


def test_validate_required_columns_raises_when_columns_missing():
    with pytest.raises(ValueError, match='missing required columns'):
        validate_required_columns(['code', 'date', 'close'])


def test_export_factor_dataset_writes_symbol_factor_parquet(tmp_path):
    output_dir = tmp_path / 'factor_pipeline' / 'output'
    df = _market_data_frame('600000')
    df['label'] = 0

    output_path = export_factor_dataset(df, '600000', output_dir=output_dir)

    assert output_path == output_dir / '600000_factor.parquet'
    saved = pd.read_parquet(output_path)
    pd.testing.assert_frame_equal(saved, df)


def test_factor_engine_runs_end_to_end(tmp_path):
    snapshot_dir = _write_snapshot(tmp_path)
    output_dir = tmp_path / 'factor_pipeline' / 'output'
    engine = FactorEngine(snapshot_dir=snapshot_dir, output_dir=output_dir)

    result = engine.run('600000')

    assert result.symbol == '600000'
    assert result.output_path == output_dir / '600000_factor.parquet'
    assert result.output_path.exists()

    saved = pd.read_parquet(result.output_path)
    assert set(saved.columns) == {*REQUIRED_COLUMNS, 'label'}
    assert saved['label'].tolist() == [0] * len(saved)
