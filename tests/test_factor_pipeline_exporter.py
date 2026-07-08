import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from factor_pipeline.io.exporter import DatasetExporter, export_factor_dataset


def _dataset_frame(rows: int = 4) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    return pd.DataFrame(
        {
            'date': dates,
            'code': '600000',
            'macd': np.arange(rows, dtype=float) + 1.0,
            'future_return': np.linspace(0.0, 0.05, rows),
            'label': [0, 1, 0, 1][:rows],
        }
    )


def test_export_creates_parquet_file(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame()

    output_path = DatasetExporter().export(df, '600000', output_dir)

    assert output_path.exists()
    assert output_path.suffix == '.parquet'


def test_export_generates_correct_filename_for_normalized_symbol(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame(rows=2)

    output_path = DatasetExporter().export(df, '1', output_dir)

    assert output_path == output_dir / '000001_factor.parquet'


def test_export_generates_correct_filename_for_six_digit_symbol(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame(rows=2)

    output_path = DatasetExporter().export(df, '600000', output_dir)

    assert output_path == output_dir / '600000_factor.parquet'


def test_export_preserves_schema(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame()

    output_path = DatasetExporter().export(df, '600000', output_dir)

    schema = pq.read_schema(output_path)
    assert schema.names == list(df.columns)
    saved = pq.read_table(output_path).to_pandas()
    assert saved['date'].dtype == df['date'].dtype
    assert saved['label'].dtype == df['label'].dtype


def test_export_preserves_column_order(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame()

    output_path = DatasetExporter().export(df, '600000', output_dir)

    saved = pq.read_table(output_path)
    assert saved.column_names == list(df.columns)


def test_export_overwrites_existing_file(tmp_path):
    output_dir = tmp_path / 'output'
    exporter = DatasetExporter()
    first = _dataset_frame(rows=2)
    second = _dataset_frame(rows=4)

    output_path = exporter.export(first, '600000', output_dir)
    exporter.export(second, '600000', output_dir)

    saved = pq.read_table(output_path).to_pandas()
    assert len(saved) == len(second)
    pd.testing.assert_frame_equal(saved, second)


def test_export_raises_for_empty_dataframe(tmp_path):
    output_dir = tmp_path / 'output'
    empty = pd.DataFrame(columns=['date', 'code', 'macd', 'future_return', 'label'])

    with pytest.raises(ValueError, match='non-empty DataFrame'):
        DatasetExporter().export(empty, '600000', output_dir)


def test_export_raises_for_empty_symbol(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame()

    with pytest.raises(ValueError, match='non-empty symbol'):
        DatasetExporter().export(df, '', output_dir)


def test_export_raises_for_whitespace_symbol(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame()

    with pytest.raises(ValueError, match='non-empty symbol'):
        DatasetExporter().export(df, '   ', output_dir)


def test_export_factor_dataset_delegates_to_exporter(tmp_path):
    output_dir = tmp_path / 'output'
    df = _dataset_frame()

    output_path = export_factor_dataset(df, '600000', output_dir=output_dir)

    assert output_path == output_dir / '600000_factor.parquet'
    saved = pq.read_table(output_path).to_pandas()
    pd.testing.assert_frame_equal(saved, df)
