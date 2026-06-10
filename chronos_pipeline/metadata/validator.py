from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .exchange import infer_exchange


@dataclass
class CrossCheckRefs:
    universe_codes: set[str]
    listed_codes: set[str]


@dataclass
class ValidationIssue:
    level: str
    message: str


@dataclass
class DiffSummary:
    added_codes: list[str] = field(default_factory=list)
    removed_codes: list[str] = field(default_factory=list)
    name_changed_codes: list[str] = field(default_factory=list)
    list_date_changed_codes: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_codes
            or self.removed_codes
            or self.name_changed_codes
            or self.list_date_changed_codes
        )


@dataclass
class ValidationReport:
    row_count: int
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    diff: DiffSummary | None = None

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'row_count': self.row_count,
            'errors': [asdict(issue) for issue in self.errors],
            'warnings': [asdict(issue) for issue in self.warnings],
        }
        if self.diff is not None:
            payload['diff'] = asdict(self.diff)
        return payload


class MetadataValidationError(Exception):
    def __init__(self, report: ValidationReport):
        self.report = report
        summary = '; '.join(issue.message for issue in report.errors[:3])
        super().__init__(f'Metadata validation failed: {summary}')


class MetadataValidator:
    MIN_ROWS = 4000
    MAX_ROWS = 6500
    MAX_REMOVED_RATIO = 0.01
    MAX_ADDED_RATIO = 0.01
    MAX_UNKNOWN_RATIO = 0.05
    MIN_LISTED_DATE_COVERAGE = 0.95
    MAX_NAME_CHANGE_COUNT = 100
    MAX_CROSS_CHECK_ONLY_IN_LISTED = 0

    @classmethod
    def validate_stock_basic(
        cls,
        df: pd.DataFrame,
        *,
        previous_df: pd.DataFrame | None = None,
        cross_check: CrossCheckRefs | None = None,
        strict: bool = False,
    ) -> ValidationReport:
        report = ValidationReport(row_count=len(df))

        cls._validate_structure(df, report)
        if previous_df is not None and not previous_df.empty:
            report.diff = cls._validate_diff(df, previous_df, report, strict=strict)
        if cross_check is not None:
            cls._validate_cross_check(df, cross_check, report, strict=strict)

        if strict and report.warnings:
            for warning in report.warnings:
                report.errors.append(
                    ValidationIssue(level='error', message=f'[strict] {warning.message}')
                )

        return report

    @classmethod
    def _validate_structure(cls, df: pd.DataFrame, report: ValidationReport) -> None:
        required_columns = {'code', 'name', 'exchange', 'status', 'list_date', 'delist_date'}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            report.errors.append(
                ValidationIssue(
                    level='error',
                    message=f'missing required columns: {sorted(missing_columns)}',
                )
            )
            return

        if not (cls.MIN_ROWS < len(df) < cls.MAX_ROWS):
            report.errors.append(
                ValidationIssue(level='error', message=f'abnormal row count: {len(df)}')
            )

        if not df['code'].is_unique:
            dup_count = df['code'].duplicated().sum()
            report.errors.append(
                ValidationIssue(level='error', message=f'duplicate code rows: {dup_count}')
            )

        if not df['code'].notna().all():
            report.errors.append(
                ValidationIssue(level='error', message='code contains null values')
            )

        if not df['name'].notna().all():
            report.errors.append(
                ValidationIssue(level='error', message='name contains null values')
            )

        if not df['code'].astype(str).str.match(r'^\d{6}$').all():
            report.errors.append(
                ValidationIssue(level='error', message='code must be 6-digit strings')
            )

        if not df['exchange'].isin(['SH', 'SZ', 'BJ', 'UNKNOWN']).all():
            report.errors.append(
                ValidationIssue(level='error', message='exchange contains invalid values')
            )

        if not df['status'].isin(['LISTED', 'UNKNOWN', 'DELISTED']).all():
            report.errors.append(
                ValidationIssue(level='error', message='status contains invalid values')
            )

        unknown_exchange_count = (df['exchange'] == 'UNKNOWN').sum()
        if unknown_exchange_count:
            report.warnings.append(
                ValidationIssue(
                    level='warning',
                    message=f'unknown exchange inferred for {unknown_exchange_count} codes',
                )
            )

        inferred = df['code'].astype(str).map(infer_exchange)
        mismatch_count = df['exchange'].ne(inferred).sum()
        if mismatch_count:
            report.errors.append(
                ValidationIssue(
                    level='error',
                    message=f'exchange prefix mismatch on {mismatch_count} codes',
                )
            )

        parsed_dates = pd.to_datetime(df['list_date'], errors='coerce')
        if parsed_dates.notna().any() and parsed_dates.gt(pd.Timestamp.today().normalize()).any():
            report.errors.append(
                ValidationIssue(level='error', message='list_date contains future dates')
            )

        listed_mask = df['status'] == 'LISTED'
        if listed_mask.any():
            listed_date_coverage = parsed_dates[listed_mask].notna().mean()
            if listed_date_coverage < cls.MIN_LISTED_DATE_COVERAGE:
                report.errors.append(
                    ValidationIssue(
                        level='error',
                        message=(
                            f'LISTED rows missing list_date: {listed_date_coverage:.2%} coverage'
                        ),
                    )
                )

        unknown_ratio = (df['status'] == 'UNKNOWN').mean()
        if unknown_ratio > cls.MAX_UNKNOWN_RATIO:
            report.warnings.append(
                ValidationIssue(
                    level='warning',
                    message=f'UNKNOWN status ratio too high: {unknown_ratio:.2%}',
                )
            )

    @classmethod
    def _validate_diff(
        cls,
        df: pd.DataFrame,
        previous_df: pd.DataFrame,
        report: ValidationReport,
        *,
        strict: bool,
    ) -> DiffSummary:
        old = previous_df.set_index('code')
        new = df.set_index('code')

        added_codes = sorted(set(new.index) - set(old.index))
        removed_codes = sorted(set(old.index) - set(new.index))

        shared_codes = sorted(set(old.index) & set(new.index))
        name_changed_codes = [
            code for code in shared_codes if str(old.at[code, 'name']) != str(new.at[code, 'name'])
        ]

        old_dates = pd.to_datetime(old['list_date'], errors='coerce')
        new_dates = pd.to_datetime(new['list_date'], errors='coerce')
        list_date_changed_codes = [
            code
            for code in shared_codes
            if (pd.isna(old_dates.at[code]) and pd.notna(new_dates.at[code]))
            or (pd.notna(old_dates.at[code]) and pd.isna(new_dates.at[code]))
            or (
                pd.notna(old_dates.at[code])
                and pd.notna(new_dates.at[code])
                and old_dates.at[code] != new_dates.at[code]
            )
        ]

        diff = DiffSummary(
            added_codes=added_codes,
            removed_codes=removed_codes,
            name_changed_codes=name_changed_codes,
            list_date_changed_codes=list_date_changed_codes,
        )

        old_count = len(old)
        if old_count:
            removed_ratio = len(removed_codes) / old_count
            added_ratio = len(added_codes) / max(len(new), 1)

            if removed_ratio > cls.MAX_REMOVED_RATIO:
                report.errors.append(
                    ValidationIssue(
                        level='error',
                        message=(
                            f'removed {len(removed_codes)} codes '
                            f'({removed_ratio:.2%} of previous snapshot)'
                        ),
                    )
                )

            if added_ratio > cls.MAX_ADDED_RATIO:
                report.warnings.append(
                    ValidationIssue(
                        level='warning',
                        message=(
                            f'added {len(added_codes)} codes '
                            f'({added_ratio:.2%} of current snapshot)'
                        ),
                    )
                )

        if len(name_changed_codes) > cls.MAX_NAME_CHANGE_COUNT:
            report.warnings.append(
                ValidationIssue(
                    level='warning',
                    message=f'name changed on {len(name_changed_codes)} codes',
                )
            )

        if list_date_changed_codes:
            report.warnings.append(
                ValidationIssue(
                    level='warning',
                    message=f'list_date changed on {len(list_date_changed_codes)} codes',
                )
            )

        if strict and diff.has_changes:
            report.warnings.append(
                ValidationIssue(
                    level='warning',
                    message='snapshot diff detected against previous parquet',
                )
            )

        return diff

    @classmethod
    def _validate_cross_check(
        cls,
        df: pd.DataFrame,
        cross_check: CrossCheckRefs,
        report: ValidationReport,
        *,
        strict: bool,
    ) -> None:
        current_codes = set(df['code'].astype(str))
        universe_codes = set(cross_check.universe_codes)
        listed_codes = set(cross_check.listed_codes)

        missing_from_output = sorted(universe_codes - current_codes)
        if missing_from_output:
            report.errors.append(
                ValidationIssue(
                    level='error',
                    message=(
                        'universe codes missing from output: '
                        f'{len(missing_from_output)} ({missing_from_output[:5]}...)'
                    ),
                )
            )

        only_in_listed = sorted(listed_codes - universe_codes)
        if len(only_in_listed) > cls.MAX_CROSS_CHECK_ONLY_IN_LISTED:
            report.errors.append(
                ValidationIssue(
                    level='error',
                    message=(
                        'listed codes missing from universe source: '
                        f'{len(only_in_listed)} ({only_in_listed[:5]}...)'
                    ),
                )
            )

        universe_only = sorted(universe_codes - listed_codes)
        universe_only_ratio = len(universe_only) / max(len(universe_codes), 1)
        if universe_only_ratio > cls.MAX_UNKNOWN_RATIO:
            report.warnings.append(
                ValidationIssue(
                    level='warning',
                    message=(
                        'universe codes without exchange list_date source: '
                        f'{len(universe_only)} ({universe_only_ratio:.2%})'
                    ),
                )
            )

        if strict and (missing_from_output or only_in_listed):
            report.warnings.append(
                ValidationIssue(
                    level='warning',
                    message='cross-check mismatch between universe and exchange sources',
                )
            )

    @staticmethod
    def write_audit(report: ValidationReport, audit_dir: Path) -> Path:
        audit_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        audit_path = audit_dir / f'{timestamp}_validation.json'
        payload = {
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            **report.to_dict(),
        }
        audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return audit_path

    @staticmethod
    def print_report(report: ValidationReport) -> None:
        for issue in report.errors:
            print(f'[ERROR] {issue.message}')
        for issue in report.warnings:
            print(f'[WARN] {issue.message}')

        if report.diff is not None and report.diff.has_changes:
            print(
                '[INFO] diff: '
                f'added={len(report.diff.added_codes)}, '
                f'removed={len(report.diff.removed_codes)}, '
                f'name_changed={len(report.diff.name_changed_codes)}, '
                f'list_date_changed={len(report.diff.list_date_changed_codes)}'
            )

        if report.passed:
            print('[OK] metadata validation passed')
