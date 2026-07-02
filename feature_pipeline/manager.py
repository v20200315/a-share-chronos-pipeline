from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from feature_pipeline.indicators import compute_macd, compute_rsi
from feature_pipeline.loader import MarketDataSnapshot, load_daily_bars, load_snapshot
from feature_pipeline.numba_ops import finite_pair_mask
from feature_pipeline.paths import MARKET_DATA_SNAPSHOT_LATEST, feature_output_dir

FEATURE_COLUMNS = [
    'code',
    'date',
    'close',
    'macd',
    'macd_signal',
    'macd_hist',
    'rsi',
    'macd_rsi_valid',
]


@dataclass(frozen=True)
class FeatureComputeResult:
    saved_paths: list[Path] = field(default_factory=list)


class FeatureManager:
    def __init__(
        self,
        *,
        snapshot_dir: str | Path = MARKET_DATA_SNAPSHOT_LATEST,
        daily_bars_dir: str | Path | None = None,
        output_dir: str | Path | None = None,
    ):
        self.snapshot_dir = Path(snapshot_dir)
        self.daily_bars_dir = Path(daily_bars_dir) if daily_bars_dir is not None else None
        self.output_dir = Path(output_dir) if output_dir is not None else feature_output_dir()

    def compute(self, *, symbols: list[str]) -> FeatureComputeResult:
        if not symbols:
            raise ValueError('symbols must not be empty')

        self.output_dir.mkdir(parents=True, exist_ok=True)
        snapshot = None if self.daily_bars_dir is not None else load_snapshot(self.snapshot_dir)
        saved_paths = [self._compute_one(symbol=symbol, snapshot=snapshot) for symbol in symbols]
        return FeatureComputeResult(saved_paths=saved_paths)

    def _compute_one(
        self,
        *,
        symbol: str,
        snapshot: MarketDataSnapshot | None,
    ) -> Path:
        daily = load_daily_bars(
            symbol,
            snapshot=snapshot,
            daily_bars_dir=self.daily_bars_dir,
        )
        features = compute_features(daily)
        output_path = self.output_dir / f'{str(symbol).zfill(6)}.parquet'
        features.to_parquet(output_path, index=False)
        return output_path


def compute_features(daily: pd.DataFrame) -> pd.DataFrame:
    close = daily['close'].to_numpy(dtype='float64')
    macd, macd_signal, macd_hist = compute_macd(close)
    rsi = compute_rsi(close)
    valid_mask = finite_pair_mask(macd, rsi)

    features = pd.DataFrame(
        {
            'code': daily['code'].astype(str).str.zfill(6),
            'date': daily['date'],
            'close': daily['close'],
            'macd': macd,
            'macd_signal': macd_signal,
            'macd_hist': macd_hist,
            'rsi': rsi,
            'macd_rsi_valid': valid_mask,
        },
        columns=FEATURE_COLUMNS,
    )
    return features
