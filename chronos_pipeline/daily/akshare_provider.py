from __future__ import annotations

from dataclasses import asdict
from datetime import date

import akshare as ak
import pandas as pd

from chronos_pipeline.models import DailyBar

from .provider import DailyBarProvider


class AkshareDailyBarProvider(DailyBarProvider):
    provider_name = 'akshare'

    COLUMN_MAP = {
        '日期': 'date',
        '开盘': 'open',
        '最高': 'high',
        '最低': 'low',
        '收盘': 'close',
        '成交量': 'volume',
        '成交额': 'amount',
        '振幅': 'amplitude',
        '涨跌幅': 'pct_change',
        '涨跌额': 'change',
        '换手率': 'turnover',
    }
    OUTPUT_COLUMNS = [
        'code',
        'date',
        'open',
        'high',
        'low',
        'close',
        'volume',
        'amount',
        'amplitude',
        'pct_change',
        'change',
        'turnover',
    ]
    NUMERIC_COLUMNS = [
        'open',
        'high',
        'low',
        'close',
        'volume',
        'amount',
        'amplitude',
        'pct_change',
        'change',
        'turnover',
    ]

    def __init__(self, *, adjust: str = 'qfq'):
        self.adjust = adjust

    def fetch_daily_bars(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        raw_df = ak.stock_zh_a_hist(
            symbol=code,
            period='daily',
            start_date=start_date.strftime('%Y%m%d'),
            end_date=end_date.strftime('%Y%m%d'),
            adjust=self.adjust,
        )
        return self._normalize(raw_df, code=code)

    @classmethod
    def _normalize(cls, df: pd.DataFrame, *, code: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=cls.OUTPUT_COLUMNS)

        normalized = df.rename(columns=cls.COLUMN_MAP).copy()
        normalized['code'] = code
        normalized['date'] = pd.to_datetime(normalized['date'], errors='coerce').dt.strftime(
            '%Y-%m-%d'
        )

        for column in cls.NUMERIC_COLUMNS:
            if column not in normalized.columns:
                normalized[column] = pd.NA
            normalized[column] = pd.to_numeric(normalized[column], errors='coerce')

        records = [
            asdict(
                DailyBar(
                    code=str(row['code']).zfill(6),
                    date=row['date'],
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume'],
                    amount=row['amount'],
                    amplitude=row['amplitude'],
                    pct_change=row['pct_change'],
                    change=row['change'],
                    turnover=row['turnover'],
                )
            )
            for _, row in normalized.iterrows()
        ]
        return pd.DataFrame.from_records(records, columns=cls.OUTPUT_COLUMNS)
