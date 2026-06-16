from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd
from tqdm.auto import tqdm

from .akshare_provider import AkshareDailyBarProvider
from .provider import DailyBarProvider


@dataclass
class DailyRefreshReport:
    saved_paths: list[Path] = field(default_factory=list)
    skipped_codes: list[str] = field(default_factory=list)
    failed_codes: list[str] = field(default_factory=list)


class DailyBarManager:
    def __init__(
        self,
        *,
        data_dir='data/daily/akshare',
        metadata_dir='data/metadata',
        metadata_provider_name: str = 'akshare',
        provider: DailyBarProvider | None = None,
        today: date | None = None,
        show_progress: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = Path(metadata_dir) / f'stock_basic_{metadata_provider_name}.parquet'
        self.provider = provider or AkshareDailyBarProvider()
        self.today = today or date.today()
        self.show_progress = show_progress

    def refresh(self, *, symbols: list[str] | None = None) -> DailyRefreshReport:
        metadata = self._load_metadata(symbols=symbols)
        report = DailyRefreshReport()

        with tqdm(
            total=len(metadata),
            desc='AKShare daily bars',
            unit='stock',
            disable=not self.show_progress,
        ) as progress:
            for row in metadata.itertuples(index=False):
                code = str(row.code).zfill(6)
                start_date = self.calculate_start_date(row.list_date, today=self.today)
                if start_date is None:
                    report.skipped_codes.append(code)
                    print(f'[WARN] skip {code}: invalid list_date={row.list_date!r}')
                    progress.update(1)
                    continue

                try:
                    df = self.provider.fetch_daily_bars(
                        code,
                        start_date=start_date,
                        end_date=self.today,
                    )
                except Exception as exc:
                    report.failed_codes.append(code)
                    print(f'[ERROR] fetch {code} failed: {exc}')
                    progress.update(1)
                    continue

                output_path = self._output_path(code)
                df.to_parquet(output_path, index=False)
                report.saved_paths.append(output_path)
                progress.update(1)
                progress.set_postfix(saved=len(report.saved_paths))

        print(
            '[INFO] daily refresh: '
            f'saved={len(report.saved_paths)}, '
            f'skipped={len(report.skipped_codes)}, '
            f'failed={len(report.failed_codes)}'
        )
        return report

    def _load_metadata(self, *, symbols: list[str] | None = None) -> pd.DataFrame:
        metadata = pd.read_parquet(self.metadata_path)
        metadata['code'] = metadata['code'].astype(str).str.zfill(6)

        if symbols is not None:
            symbol_set = {str(symbol).zfill(6) for symbol in symbols}
            metadata = metadata[metadata['code'].isin(symbol_set)]

        return metadata.sort_values('code')

    @staticmethod
    def calculate_start_date(list_date: str | None, *, today: date | None = None) -> date | None:
        parsed_list_date = pd.to_datetime(list_date, format='%Y-%m-%d', errors='coerce')
        if pd.isna(parsed_list_date):
            return None

        current_date = today or date.today()
        five_year_start = (pd.Timestamp(current_date) - pd.DateOffset(years=5)).date()
        actual_list_date = parsed_list_date.date()
        return max(five_year_start, actual_list_date)

    def _output_path(self, code: str) -> Path:
        return self.data_dir / f'{code}.parquet'
