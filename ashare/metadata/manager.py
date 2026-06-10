from pathlib import Path

import pandas as pd

from .akshare_provider import AkshareMetadataProvider
from .validator import MetadataValidationError, MetadataValidator


class MetadataManager:
    def __init__(self, data_dir='data/metadata'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.file_path = self.data_dir / 'stock_basic.parquet'
        self.audit_dir = self.data_dir / 'audit'
        self.provider = AkshareMetadataProvider()

    def refresh(self, *, strict: bool = False):
        """重新生成 metadata，校验通过后才写入 parquet。"""

        df = self.provider.fetch_stock_basic()
        df = df.drop_duplicates(subset=['code'])
        df = df.sort_values('code')

        previous_df = None
        if self.file_path.exists():
            previous_df = pd.read_parquet(self.file_path)

        report = MetadataValidator.validate_stock_basic(
            df,
            previous_df=previous_df,
            cross_check=self.provider.last_cross_check,
            strict=strict,
        )
        audit_path = MetadataValidator.write_audit(report, self.audit_dir)
        MetadataValidator.print_report(report)
        print(f'[INFO] audit -> {audit_path}')

        if not report.passed:
            raise MetadataValidationError(report)

        df.to_parquet(self.file_path, index=False)

        print(f'[OK] saved -> {self.file_path}')
        print(f'[INFO] total stocks: {len(df)}')

        return df

    def load(self):
        return pd.read_parquet(self.file_path)

    def get_symbols(self):
        return self.load()['code'].tolist()
