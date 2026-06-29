from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm.auto import tqdm

from .akshare_provider import AkshareDailyBarProvider
from .provider import DailyBarProvider


@dataclass
class DailyRefreshReport:
    saved_paths: list[Path] = field(default_factory=list)
    skipped_codes: list[str] = field(default_factory=list)
    failed_codes: list[str] = field(default_factory=list)
    skipped_reasons: dict[str, str] = field(default_factory=dict)
    failed_reasons: dict[str, str] = field(default_factory=dict)
    report_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'saved_count': len(self.saved_paths),
            'skipped_count': len(self.skipped_codes),
            'failed_count': len(self.failed_codes),
            'skipped_codes': self.skipped_codes,
            'failed_codes': self.failed_codes,
            'skipped_reasons': self.skipped_reasons,
            'failed_reasons': self.failed_reasons,
            'report_path': str(self.report_path) if self.report_path is not None else None,
        }


@dataclass
class _DailyTaskResult:
    order: int
    code: str
    status: str
    output_path: Path | None = None
    error: Exception | None = None
    list_date: Any = None


class DailyBarManager:
    COVERAGE_TOLERANCE_DAYS = 7

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
        self.audit_dir = self.data_dir / 'audit'
        self.metadata_path = Path(metadata_dir) / f'stock_basic_{metadata_provider_name}.parquet'
        self.provider = provider or AkshareDailyBarProvider()
        self.today = today or date.today()
        self.show_progress = show_progress

    def refresh(
        self,
        *,
        symbols: list[str] | None = None,
        top: int | None = None,
        max_concurrency: int = 8,
    ) -> DailyRefreshReport:
        if max_concurrency <= 0:
            raise ValueError('max_concurrency must be a positive integer')

        metadata = self._load_metadata(symbols=symbols, top=top)
        print(
            f'[INFO] daily refresh start: stocks={len(metadata)}, max_concurrency={max_concurrency}'
        )
        report = asyncio.run(
            self._refresh_async(metadata=metadata, max_concurrency=max_concurrency)
        )
        print(
            '[INFO] daily refresh: '
            f'saved={len(report.saved_paths)}, '
            f'skipped={len(report.skipped_codes)}, '
            f'failed={len(report.failed_codes)}'
        )
        report.report_path = self._write_report(report)
        print(f'[INFO] daily report -> {report.report_path}')
        return report

    async def _refresh_async(
        self,
        *,
        metadata: pd.DataFrame,
        max_concurrency: int,
    ) -> DailyRefreshReport:
        report = DailyRefreshReport()
        semaphore = asyncio.Semaphore(max_concurrency)
        results: list[_DailyTaskResult] = []

        with tqdm(
            total=len(metadata),
            desc='AKShare daily bars',
            unit='stock',
            disable=not self.show_progress,
        ) as progress:
            tasks = [
                self._refresh_one(row=row, order=order, semaphore=semaphore)
                for order, row in enumerate(metadata.itertuples(index=False))
            ]
            for task in asyncio.as_completed(tasks):
                result = await task
                results.append(result)
                if result.status == 'skipped':
                    print(f'[WARN] skip {result.code}: invalid list_date={result.list_date!r}')
                elif result.status == 'failed':
                    print(f'[ERROR] fetch {result.code} failed: {result.error}')
                progress.update(1)
                saved_count = sum(item.status == 'saved' for item in results)
                progress.set_postfix(saved=saved_count)

        ordered_results = sorted(results, key=lambda item: item.order)
        report.saved_paths = [
            result.output_path
            for result in ordered_results
            if result.status == 'saved' and result.output_path is not None
        ]
        report.skipped_codes = [
            result.code for result in ordered_results if result.status == 'skipped'
        ]
        report.failed_codes = [
            result.code for result in ordered_results if result.status == 'failed'
        ]
        report.skipped_reasons = {
            result.code: f'invalid list_date={result.list_date!r}'
            for result in ordered_results
            if result.status == 'skipped'
        }
        report.failed_reasons = {
            result.code: str(result.error)
            for result in ordered_results
            if result.status == 'failed' and result.error is not None
        }
        return report

    async def _refresh_one(
        self,
        *,
        row,
        order: int,
        semaphore: asyncio.Semaphore,
    ) -> _DailyTaskResult:
        code = str(row.code).zfill(6)
        start_date = self.calculate_start_date(row.list_date, today=self.today)
        if start_date is None:
            return _DailyTaskResult(
                order=order,
                code=code,
                status='skipped',
                list_date=row.list_date,
            )

        async with semaphore:
            try:
                df = await asyncio.to_thread(
                    self.provider.fetch_daily_bars,
                    code,
                    start_date=start_date,
                    end_date=self.today,
                )
                coverage_error = self._coverage_error(
                    df,
                    start_date=start_date,
                    end_date=self.today,
                )
                if coverage_error is not None:
                    raise ValueError(coverage_error)

                output_path = self._output_path(code)
                await asyncio.to_thread(df.to_parquet, output_path, index=False)
            except Exception as exc:
                return _DailyTaskResult(
                    order=order,
                    code=code,
                    status='failed',
                    error=exc,
                )

        return _DailyTaskResult(
            order=order,
            code=code,
            status='saved',
            output_path=output_path,
        )

    def _load_metadata(
        self,
        *,
        symbols: list[str] | None = None,
        top: int | None = None,
    ) -> pd.DataFrame:
        if top is not None and top <= 0:
            raise ValueError('top must be a positive integer')

        metadata = pd.read_parquet(self.metadata_path)
        metadata['code'] = metadata['code'].astype(str).str.zfill(6)

        if symbols is not None:
            symbol_set = {str(symbol).zfill(6) for symbol in symbols}
            metadata = metadata[metadata['code'].isin(symbol_set)]

        metadata = metadata.sort_values('code')
        if top is not None:
            metadata = metadata.head(top)

        return metadata

    @staticmethod
    def calculate_start_date(list_date: str | None, *, today: date | None = None) -> date | None:
        parsed_list_date = pd.to_datetime(list_date, format='%Y-%m-%d', errors='coerce')
        if pd.isna(parsed_list_date):
            return None

        current_date = today or date.today()
        five_year_start = (pd.Timestamp(current_date) - pd.DateOffset(years=5)).date()
        actual_list_date = parsed_list_date.date()
        return max(five_year_start, actual_list_date)

    @classmethod
    def _coverage_error(
        cls,
        df: pd.DataFrame,
        *,
        start_date: date,
        end_date: date,
    ) -> str | None:
        if df.empty:
            return 'daily bars are empty'

        if 'date' not in df.columns:
            return 'daily bars missing date column'

        parsed_dates = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')
        valid_dates = parsed_dates.dropna()
        if valid_dates.empty:
            return 'daily bars contain no valid dates'

        first_date = valid_dates.min().date()
        last_date = valid_dates.max().date()
        first_acceptable_date = start_date + timedelta(days=cls.COVERAGE_TOLERANCE_DAYS)
        last_acceptable_date = end_date - timedelta(days=cls.COVERAGE_TOLERANCE_DAYS)

        if first_date > first_acceptable_date:
            return (
                'daily bars start too late: '
                f'first_date={first_date}, expected_on_or_before={first_acceptable_date}'
            )

        if last_date < last_acceptable_date:
            return (
                'daily bars end too early: '
                f'last_date={last_date}, expected_on_or_after={last_acceptable_date}'
            )

        return None

    def _output_path(self, code: str) -> Path:
        return self.data_dir / f'{code}.parquet'

    def _write_report(self, report: DailyRefreshReport) -> Path:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        report_path = self.audit_dir / f'{timestamp}_daily_refresh.json'
        report.report_path = report_path
        payload = {
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'metadata_path': str(self.metadata_path),
            'data_dir': str(self.data_dir),
            'today': self.today.isoformat(),
            **report.to_dict(),
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return report_path
