import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import talib

from feature_pipeline.loader import load_daily_bars, load_snapshot
from feature_pipeline.manager import FEATURE_COLUMNS, FeatureManager, compute_features


def _daily_frame(code: str, rows: int = 80, *, reverse: bool = False) -> pd.DataFrame:
    dates = pd.date_range('2024-01-01', periods=rows, freq='D')
    close = np.linspace(10.0, 20.0, rows) + np.sin(np.arange(rows) / 3)
    df = pd.DataFrame(
        {
            'code': code,
            'date': dates.strftime('%Y-%m-%d'),
            'open': close - 0.1,
            'high': close + 0.5,
            'low': close - 0.5,
            'close': close,
            'volume': np.arange(rows) + 1000,
        }
    )
    if reverse:
        return df.iloc[::-1].reset_index(drop=True)
    return df


def _write_snapshot(tmp_path: Path) -> Path:
    snapshot_dir = tmp_path / 'snapshot'
    daily_bars_dir = snapshot_dir / 'daily_bars'
    daily_bars_dir.mkdir(parents=True)
    _daily_frame('000001', reverse=True).to_parquet(daily_bars_dir / '000001.parquet', index=False)
    _daily_frame('600000').to_parquet(daily_bars_dir / '600000.parquet', index=False)
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


def test_load_daily_bars_reads_snapshot_contract_and_sorts_dates(tmp_path):
    snapshot = load_snapshot(_write_snapshot(tmp_path))

    daily = load_daily_bars('1', snapshot=snapshot)

    assert daily['code'].unique().tolist() == ['000001']
    assert daily['date'].tolist() == sorted(daily['date'].tolist())
    assert daily[['code', 'date', 'close']].isna().sum().sum() == 0


def test_compute_features_matches_talib_macd_and_rsi():
    daily = _daily_frame('000001')

    features = compute_features(daily)

    close = daily['close'].to_numpy(dtype='float64')
    expected_macd, expected_signal, expected_hist = talib.MACD(close)
    expected_rsi = talib.RSI(close)
    assert list(features.columns) == FEATURE_COLUMNS
    assert len(features) == len(daily)
    np.testing.assert_allclose(features['macd'].to_numpy(), expected_macd, equal_nan=True)
    np.testing.assert_allclose(features['macd_signal'].to_numpy(), expected_signal, equal_nan=True)
    np.testing.assert_allclose(features['macd_hist'].to_numpy(), expected_hist, equal_nan=True)
    np.testing.assert_allclose(features['rsi'].to_numpy(), expected_rsi, equal_nan=True)
    assert features['macd'].isna().iloc[0]
    assert features['rsi'].isna().iloc[0]
    assert features['macd_rsi_valid'].iloc[-1]


def test_feature_manager_writes_selected_symbols_from_snapshot(tmp_path):
    snapshot_dir = _write_snapshot(tmp_path)
    output_dir = tmp_path / 'features'
    manager = FeatureManager(snapshot_dir=snapshot_dir, output_dir=output_dir)

    result = manager.compute(symbols=['000001', '600000'])

    assert [path.name for path in result.saved_paths] == ['000001.parquet', '600000.parquet']
    saved = pd.read_parquet(output_dir / '000001.parquet')
    assert list(saved.columns) == FEATURE_COLUMNS
    assert saved['code'].unique().tolist() == ['000001']


def test_feature_pipeline_production_code_does_not_import_market_data_pipeline():
    feature_files = Path('feature_pipeline').glob('**/*.py')
    offenders = []
    for feature_file in feature_files:
        tree = ast.parse(feature_file.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            else:
                continue
            if any(name == 'market_data_pipeline' or name.startswith('market_data_pipeline.') for name in names):
                offenders.append(str(feature_file))

    assert offenders == []
