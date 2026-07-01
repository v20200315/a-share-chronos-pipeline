import argparse
import sys

from market_data_pipeline.daily.manager import DailyBarManager
from market_data_pipeline.metadata.akshare_provider import AkshareMetadataProvider
from market_data_pipeline.metadata.eastmoney_provider import EastMoneyMetadataProvider
from market_data_pipeline.metadata.manager import MetadataManager
from market_data_pipeline.metadata.provider import MetadataProvider
from market_data_pipeline.metadata.validator import MetadataValidationError
from market_data_pipeline.snapshot import MarketDataSnapshotPublisher


def create_provider(name: str) -> MetadataProvider:
    if name == 'akshare':
        return AkshareMetadataProvider()
    if name == 'eastmoney':
        return EastMoneyMetadataProvider()

    raise ValueError(f'unsupported provider: {name}')


def parse_symbols(value: str | None) -> list[str] | None:
    if value is None:
        return None

    return [symbol.strip() for symbol in value.split(',') if symbol.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'command',
        choices=['refresh', 'validate', 'clean', 'load', 'daily-refresh', 'publish-snapshot'],
    )
    parser.add_argument(
        '--provider',
        choices=['akshare', 'eastmoney'],
        default='akshare',
        help='metadata source used by refresh/validate/clean/load',
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='treat validation warnings as errors',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='show cleanup impact without modifying parquet',
    )
    parser.add_argument(
        '--metadata-provider',
        choices=['akshare', 'eastmoney'],
        default='akshare',
        help='metadata parquet used by daily-refresh',
    )
    parser.add_argument(
        '--symbols',
        help='comma-separated stock codes used by daily-refresh, for example 600519,000001',
    )
    parser.add_argument(
        '--top',
        type=int,
        help='fetch daily bars for the first N stocks after metadata filtering',
    )
    parser.add_argument(
        '--max-concurrency',
        type=int,
        default=8,
        help='maximum concurrent daily-refresh fetches',
    )
    parser.add_argument(
        '--snapshot-name',
        help='snapshot directory name used by publish-snapshot; defaults to a timestamp',
    )

    args = parser.parse_args()

    if args.command == 'refresh':
        manager = MetadataManager(provider=create_provider(args.provider))
        manager.refresh()

    elif args.command == 'validate':
        manager = MetadataManager(provider=create_provider(args.provider))
        try:
            manager.validate(strict=args.strict)
        except MetadataValidationError as exc:
            print(f'[FAIL] {exc}', file=sys.stderr)
            sys.exit(1)

    elif args.command == 'clean':
        manager = MetadataManager(provider=create_provider(args.provider))
        manager.clean(strict=args.strict, dry_run=args.dry_run)

    elif args.command == 'load':
        manager = MetadataManager(provider=create_provider(args.provider))
        df = manager.load()
        print(df.head())

    elif args.command == 'daily-refresh':
        daily_manager = DailyBarManager(metadata_provider_name=args.metadata_provider)
        try:
            daily_manager.refresh(
                symbols=parse_symbols(args.symbols),
                top=args.top,
                max_concurrency=args.max_concurrency,
            )
        except ValueError as exc:
            print(f'[FAIL] {exc}', file=sys.stderr)
            sys.exit(1)

    elif args.command == 'publish-snapshot':
        publisher = MarketDataSnapshotPublisher(metadata_provider_name=args.metadata_provider)
        try:
            result = publisher.publish(snapshot_name=args.snapshot_name)
        except FileNotFoundError as exc:
            print(f'[FAIL] {exc}', file=sys.stderr)
            sys.exit(1)
        print(f'[OK] snapshot -> {result.snapshot_dir}')
        print(f'[INFO] manifest -> {result.manifest_path}')
        if result.latest_dir is not None:
            print(f'[OK] latest snapshot -> {result.latest_dir}')


if __name__ == '__main__':
    main()
