from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from math import ceil
from typing import Any

import httpx
import pandas as pd
from tqdm.auto import tqdm

from chronos_pipeline.models import StockBasic

from .exchange import infer_exchange
from .provider import MetadataProvider


class EastMoneyMetadataProvider(MetadataProvider):
    provider_name = 'eastmoney'

    BASE_URL = 'https://push2.eastmoney.com/webguest/api/qt/clist/get'
    DEFAULT_FIELDS = 'f3,f12,f14,f26'
    DEFAULT_FILTER = 'm:0+t:6+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:81+s:262144+f:!2'

    def __init__(
        self,
        *,
        page_size: int = 100,
        timeout: float = 15.0,
        request_interval_seconds: float = 0.5,
        max_concurrency: int = 8,
        show_progress: bool = True,
    ):
        self.page_size = page_size
        self.timeout = timeout
        self.request_interval_seconds = request_interval_seconds
        self.max_concurrency = max_concurrency
        self.show_progress = show_progress

    def fetch_stock_basic(self) -> pd.DataFrame:
        rows = self._fetch_all_rows()
        return self._normalize_rows(rows)

    def _fetch_all_rows(self) -> list[dict[str, Any]]:
        return asyncio.run(self._fetch_all_rows_async())

    async def _fetch_all_rows_async(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            first_page = await self._fetch_page(client, 1)
            data = first_page.get('data') or {}
            first_page_rows = data.get('diff') or []
            total = int(data.get('total') or len(first_page_rows))
            page_count = self._page_count(total, self.page_size)
            print(
                f'[INFO] EastMoney total={total} pages={page_count} pz={self.page_size}',
                flush=True,
            )

            with tqdm(
                total=page_count,
                desc='EastMoney metadata',
                unit='page',
                disable=not self.show_progress,
            ) as progress:
                progress.update(1)
                progress.set_postfix(rows=len(first_page_rows))

                page_rows_by_page: dict[int, list[dict[str, Any]]] = {
                    1: first_page_rows,
                }
                semaphore = asyncio.Semaphore(self.max_concurrency)
                tasks = [
                    self._fetch_page_rows(client, page, semaphore)
                    for page in range(2, page_count + 1)
                ]
                for task in asyncio.as_completed(tasks):
                    page, page_rows = await task
                    page_rows_by_page[page] = page_rows
                    progress.update(1)
                    retrieved_rows = sum(len(rows) for rows in page_rows_by_page.values())
                    progress.set_postfix(rows=retrieved_rows)

        print(f'[INFO] EastMoney requests sent: {page_count}', flush=True)
        rows = [
            row
            for page in range(1, page_count + 1)
            for row in page_rows_by_page.get(page, [])
        ]
        print(f'[INFO] EastMoney retrieved rows: {len(rows)}', flush=True)
        return rows

    async def _fetch_page_rows(
        self,
        client: httpx.AsyncClient,
        page: int,
        semaphore: asyncio.Semaphore,
    ) -> tuple[int, list[dict[str, Any]]]:
        async with semaphore:
            page_data = (await self._fetch_page(client, page)).get('data') or {}
            return page, page_data.get('diff') or []

    async def _fetch_page(self, client: httpx.AsyncClient, page: int) -> dict[str, Any]:
        response = await client.get(self.BASE_URL, params=self._build_params(page))
        response.raise_for_status()
        if self.request_interval_seconds:
            await asyncio.sleep(self.request_interval_seconds)
        return self._parse_jsonp(response.text)

    @staticmethod
    def _page_count(total: int, page_size: int) -> int:
        return max(1, ceil(total / page_size))

    def _build_params(self, page: int) -> dict[str, str | int]:
        timestamp = int(time.time() * 1000)
        callback = f'jQuery37106414938370754382_{timestamp}'
        return {
            'np': '1',
            'fltt': '1',
            'invt': '2',
            'cb': callback,
            'fs': self.DEFAULT_FILTER,
            'fields': self.DEFAULT_FIELDS,
            'fid': 'f12',
            'pn': page,
            'pz': self.page_size,
            'po': '1',
            'dect': '1',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'wbp2u': '|0|0|0|web',
            '_': timestamp + 95,
        }

    @staticmethod
    def _parse_jsonp(text: str) -> dict[str, Any]:
        stripped = text.strip()
        start = stripped.find('(')
        end = stripped.rfind(')')
        if start == -1 or end == -1 or end <= start:
            raise ValueError('EastMoney response is not valid JSONP')

        return json.loads(stripped[start + 1 : end])

    @classmethod
    def _normalize_rows(cls, rows: list[dict[str, Any]]) -> pd.DataFrame:
        records = [asdict(cls._row_to_stock_basic(row)) for row in rows]
        return pd.DataFrame.from_records(
            records,
            columns=['code', 'name', 'exchange', 'list_date'],
        )

    @staticmethod
    def _row_to_stock_basic(row: dict[str, Any]) -> StockBasic:
        code = str(row.get('f12') or '').zfill(6)
        return StockBasic(
            code=code,
            name=str(row.get('f14') or '').strip(),
            exchange=infer_exchange(code),
            list_date=EastMoneyMetadataProvider._normalize_list_date(row.get('f26')),
        )

    @staticmethod
    def _normalize_list_date(value: Any) -> str | None:
        if value in (None, '', '-', 0, '0'):
            return None

        parsed = pd.to_datetime(str(value), format='%Y%m%d', errors='coerce')
        if pd.isna(parsed):
            parsed = pd.to_datetime(value, errors='coerce')
        if pd.isna(parsed):
            return None

        return parsed.strftime('%Y-%m-%d')
