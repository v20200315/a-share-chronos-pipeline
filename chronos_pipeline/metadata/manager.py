from pathlib import Path

import pandas as pd

from .akshare_provider import AkshareMetadataProvider
from .akshare_validator import AkshareMetadataValidator
from .eastmoney_validator import EastMoneyMetadataValidator
from .provider import MetadataProvider
from .validator import MetadataValidationError, MetadataValidator

VALIDATORS: dict[str, type[MetadataValidator]] = {
    AkshareMetadataValidator.provider_name: AkshareMetadataValidator,
    EastMoneyMetadataValidator.provider_name: EastMoneyMetadataValidator,
}


class MetadataManager:
    def __init__(self, data_dir='data/metadata', provider: MetadataProvider | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.provider = provider or AkshareMetadataProvider()
        self.file_path = self.data_dir / f'stock_basic_{self.provider.provider_name}.parquet'
        self.audit_dir = self.data_dir / 'audit' / self.provider.provider_name

    def refresh(self):
        """Fetch metadata and write it without validation."""

        df = self.provider.fetch_stock_basic()
        df = df.sort_values('code')

        df.to_parquet(self.file_path, index=False)

        print(f'[OK] saved -> {self.file_path}')
        print(f'[INFO] total stocks: {len(df)}')

        return df

    def validate(self, *, strict: bool = False):
        df = self.load()
        validator = self._validator()
        report = validator.validate_stock_basic(df, strict=strict)
        audit_path = validator.write_audit(report, self.audit_dir)
        validator.print_report(report)
        print(f'[INFO] audit -> {audit_path}')

        if not report.passed:
            raise MetadataValidationError(report)

        return report

    def clean(self, *, strict: bool = False, dry_run: bool = False):
        df = self.load()
        validator = self._validator()
        cleaned, report = validator.clean_stock_basic(df, strict=strict)

        if report.changed:
            print(
                '[INFO] cleanup: '
                f'before={report.row_count_before}, '
                f'after={report.row_count_after}, '
                f'removed={report.removed_count}'
            )
            print(f'[INFO] removed codes: {", ".join(report.removed_codes)}')
        else:
            print('[OK] cleanup: no removable row errors found')

        if dry_run:
            print('[INFO] dry-run: parquet not modified')
            return cleaned, report

        if report.changed:
            cleaned.to_parquet(self.file_path, index=False)
            print(f'[OK] cleaned -> {self.file_path}')

        return cleaned, report

    def _validator(self) -> type[MetadataValidator]:
        try:
            return VALIDATORS[self.provider.provider_name]
        except KeyError as exc:
            raise ValueError(
                f'unsupported provider validator: {self.provider.provider_name}'
            ) from exc

    def load(self):
        return pd.read_parquet(self.file_path)

    def get_symbols(self):
        return self.load()['code'].tolist()
