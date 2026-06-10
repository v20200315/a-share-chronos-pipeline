import akshare as ak
import pandas as pd

from .exchange import infer_exchange
from .provider import MetadataProvider
from .validator import CrossCheckRefs


class AkshareMetadataProvider(MetadataProvider):
    def __init__(self):
        self._last_cross_check: CrossCheckRefs | None = None

    @property
    def last_cross_check(self) -> CrossCheckRefs | None:
        return self._last_cross_check

    def fetch_stock_basic(self) -> pd.DataFrame:

        # 全量A股（5526）
        all_df = ak.stock_info_a_code_name()[['code', 'name']]
        universe_codes = set(all_df['code'].astype(str))

        # 沪市
        sh = ak.stock_info_sh_name_code()
        sh = sh.rename(columns={'证券代码': 'code', '证券简称': 'name', '上市日期': 'list_date'})
        sh['exchange'] = 'SH'

        # 深市
        sz = ak.stock_info_sz_name_code()
        sz = sz.rename(columns={'A股代码': 'code', 'A股简称': 'name', 'A股上市日期': 'list_date'})
        sz['exchange'] = 'SZ'

        # 北交所
        bj = ak.stock_info_bj_name_code()
        bj = bj.rename(columns={'证券代码': 'code', '证券简称': 'name', '上市日期': 'list_date'})
        bj['exchange'] = 'BJ'

        listed = pd.concat([sh, sz, bj], ignore_index=True)
        listed_codes = set(listed['code'].astype(str))
        self._last_cross_check = CrossCheckRefs(
            universe_codes=universe_codes,
            listed_codes=listed_codes,
        )

        df = all_df.merge(listed[['code', 'list_date']], on='code', how='left')

        parsed_dates = pd.to_datetime(df['list_date'], errors='coerce')
        df['list_date'] = parsed_dates.dt.strftime('%Y-%m-%d').astype('string')

        df['status'] = parsed_dates.notna().map({True: 'LISTED', False: 'UNKNOWN'})
        df['delist_date'] = pd.Series(pd.NA, index=df.index, dtype='string')
        df['exchange'] = df['code'].astype(str).map(infer_exchange)

        return df
