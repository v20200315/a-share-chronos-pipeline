from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from market_data_pipeline.paths import (
    DEFAULT_DAILY_ADJUST,
    DEFAULT_DAILY_FREQUENCY,
    DEFAULT_DAILY_PROVIDER,
    MARKET_DATA_SNAPSHOTS_ROOT,
    daily_bars_dir,
    metadata_file_path,
)


@dataclass(frozen=True)
class SnapshotPublishResult:
    snapshot_dir: Path
    manifest_path: Path
    latest_dir: Path | None = None


class MarketDataSnapshotPublisher:
    def __init__(
        self,
        *,
        metadata_provider_name: str = 'akshare',
        daily_provider_name: str = DEFAULT_DAILY_PROVIDER,
        adjust: str = DEFAULT_DAILY_ADJUST,
        frequency: str = DEFAULT_DAILY_FREQUENCY,
        metadata_path: str | Path | None = None,
        daily_dir: str | Path | None = None,
        snapshots_root: str | Path = MARKET_DATA_SNAPSHOTS_ROOT,
    ):
        self.metadata_provider_name = metadata_provider_name
        self.daily_provider_name = daily_provider_name
        self.adjust = adjust
        self.frequency = frequency
        self.metadata_path = (
            Path(metadata_path)
            if metadata_path is not None
            else metadata_file_path(metadata_provider_name)
        )
        self.daily_dir = (
            Path(daily_dir)
            if daily_dir is not None
            else daily_bars_dir(
                provider_name=daily_provider_name,
                adjust=adjust,
                frequency=frequency,
            )
        )
        self.snapshots_root = Path(snapshots_root)

    def publish(
        self,
        *,
        snapshot_name: str | None = None,
        update_latest: bool = True,
    ) -> SnapshotPublishResult:
        actual_snapshot_name = snapshot_name or datetime.now().strftime('%Y-%m-%dT%H%M%S')
        snapshot_dir = self.snapshots_root / actual_snapshot_name
        manifest_path = self._write_snapshot(snapshot_dir)

        latest_dir = None
        if update_latest and actual_snapshot_name != 'latest':
            latest_dir = self.snapshots_root / 'latest'
            self._write_snapshot(latest_dir)

        return SnapshotPublishResult(
            snapshot_dir=snapshot_dir,
            manifest_path=manifest_path,
            latest_dir=latest_dir,
        )

    def _write_snapshot(self, target_dir: Path) -> Path:
        if not self.metadata_path.exists():
            raise FileNotFoundError(f'metadata parquet not found: {self.metadata_path}')
        if not self.daily_dir.exists():
            raise FileNotFoundError(f'daily bars directory not found: {self.daily_dir}')

        if target_dir.exists():
            shutil.rmtree(target_dir)
        daily_target_dir = target_dir / 'daily_bars'
        daily_target_dir.mkdir(parents=True, exist_ok=True)

        stock_basic_path = target_dir / 'stock_basic.parquet'
        shutil.copy2(self.metadata_path, stock_basic_path)

        daily_files = sorted(self.daily_dir.glob('*.parquet'))
        for daily_file in daily_files:
            shutil.copy2(daily_file, daily_target_dir / daily_file.name)

        manifest = self._manifest(
            snapshot_dir=target_dir,
            stock_basic_path=stock_basic_path,
            daily_target_dir=daily_target_dir,
            daily_files=daily_files,
        )
        manifest_path = target_dir / 'manifest.json'
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        return manifest_path

    def _manifest(
        self,
        *,
        snapshot_dir: Path,
        stock_basic_path: Path,
        daily_target_dir: Path,
        daily_files: list[Path],
    ) -> dict[str, Any]:
        symbols = [path.stem for path in daily_files]
        return {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'snapshot_dir': str(snapshot_dir),
            'metadata_provider': self.metadata_provider_name,
            'daily_bars_provider': self.daily_provider_name,
            'adjust': self.adjust,
            'frequency': self.frequency,
            'metadata_path': str(stock_basic_path),
            'daily_bars_path': str(daily_target_dir),
            'source_metadata_path': str(self.metadata_path),
            'source_daily_bars_path': str(self.daily_dir),
            'symbol_count': len(symbols),
            'symbols': symbols,
            'date_coverage': self._date_coverage(daily_files),
        }

    @staticmethod
    def _date_coverage(daily_files: list[Path]) -> dict[str, str | None]:
        first_dates = []
        last_dates = []
        for daily_file in daily_files:
            df = pd.read_parquet(daily_file, columns=['date'])
            parsed_dates = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce').dropna()
            if parsed_dates.empty:
                continue
            first_dates.append(parsed_dates.min())
            last_dates.append(parsed_dates.max())

        if not first_dates or not last_dates:
            return {'start_date': None, 'end_date': None}

        return {
            'start_date': min(first_dates).strftime('%Y-%m-%d'),
            'end_date': max(last_dates).strftime('%Y-%m-%d'),
        }
