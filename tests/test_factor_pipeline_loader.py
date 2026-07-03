from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factor_pipeline.engine import FactorEngine
from factor_pipeline.io.exporter import export_factor_dataset
from factor_pipeline.io.loader import REQUIRED_COLUMNS, load_market_data


def _market_data_frame(code: str, rows: int = 5) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 15.0, rows)
    return pd.DataFrame(
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


def _write_market_data_input(tmp_path: Path, code: str = '600000') -> Path:
    input_dir = tmp_path / 'market_data_pipeline' / 'output'
    input_dir.mkdir(parents=True)
    _market_data_frame(code).to_parquet(input_dir / f'{code}.parquet', index=False)
    return input_dir


def test_load_market_data_reads_one_symbol_parquet(tmp_path):
    input_dir = _write_market_data_input(tmp_path)
    expected = pd.read_parquet(input_dir / '600000.parquet')

    loaded = load_market_data('600000', input_dir=input_dir)

    pd.testing.assert_frame_equal(loaded, expected)


def test_load_market_data_normalizes_symbol_to_six_digits(tmp_path):
    input_dir = _write_market_data_input(tmp_path, code='000001')
    expected = pd.read_parquet(input_dir / '000001.parquet')

    loaded = load_market_data('1', input_dir=input_dir)

    pd.testing.assert_frame_equal(loaded, expected)


def test_load_market_data_raises_when_parquet_missing(tmp_path):
    input_dir = _write_market_data_input(tmp_path)

    with pytest.raises(FileNotFoundError, match='market data parquet not found'):
        load_market_data('999999', input_dir=input_dir)


def test_load_market_data_raises_when_required_columns_missing(tmp_path):
    input_dir = tmp_path / 'input'
    input_dir.mkdir()
    pd.DataFrame({'code': ['600000'], 'date': ['2024-01-01'], 'close': [10.0]}).to_parquet(
        input_dir / '600000.parquet',
        index=False,
    )

    with pytest.raises(ValueError, match='missing required columns'):
        load_market_data('600000', input_dir=input_dir)


def test_export_factor_dataset_writes_symbol_factor_parquet(tmp_path):
    output_dir = tmp_path / 'factor_pipeline' / 'output'
    df = _market_data_frame('600000')
    df['label'] = 0

    output_path = export_factor_dataset(df, '600000', output_dir=output_dir)

    assert output_path == output_dir / '600000_factor.parquet'
    saved = pd.read_parquet(output_path)
    pd.testing.assert_frame_equal(saved, df)


def test_factor_engine_runs_end_to_end(tmp_path):
    input_dir = _write_market_data_input(tmp_path)
    output_dir = tmp_path / 'factor_pipeline' / 'output'
    engine = FactorEngine(input_dir=input_dir, output_dir=output_dir)

    result = engine.run('600000')

    assert result.symbol == '600000'
    assert result.output_path == output_dir / '600000_factor.parquet'
    assert result.output_path.exists()

    saved = pd.read_parquet(result.output_path)
    assert list(saved.columns) == [*REQUIRED_COLUMNS, 'label']
    assert saved['label'].tolist() == [0] * len(saved)
