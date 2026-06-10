from pathlib import Path

import pandas as pd

from .akshare_provider import AkshareMetadataProvider


class MetadataManager:
    def __init__(self, data_dir='data/metadata'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.file_path = self.data_dir / 'stock_basic.parquet'
        self.provider = AkshareMetadataProvider()

    def refresh(self):
        """重新生成 metadata"""

        df = self.provider.fetch_stock_basic()

        df = df.drop_duplicates(subset=['code'])
        df = df.sort_values('code')

        df.to_parquet(self.file_path, index=False)

        print(f'[OK] saved -> {self.file_path}')
        print(f'[INFO] total stocks: {len(df)}')

        return df

    def load(self):
        return pd.read_parquet(self.file_path)

    def get_symbols(self):
        return self.load()['code'].tolist()
