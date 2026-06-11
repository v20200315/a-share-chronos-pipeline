import argparse
import sys

from chronos_pipeline.metadata.akshare_provider import AkshareMetadataProvider
from chronos_pipeline.metadata.eastmoney_provider import EastMoneyMetadataProvider
from chronos_pipeline.metadata.manager import MetadataManager
from chronos_pipeline.metadata.provider import MetadataProvider
from chronos_pipeline.metadata.validator import MetadataValidationError


def create_provider(name: str) -> MetadataProvider:
    if name == 'akshare':
        return AkshareMetadataProvider()
    if name == 'eastmoney':
        return EastMoneyMetadataProvider()

    raise ValueError(f'unsupported provider: {name}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['refresh', 'load'])
    parser.add_argument(
        '--provider',
        choices=['akshare', 'eastmoney'],
        default='akshare',
        help='metadata source used by refresh/load',
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='treat validation warnings as errors',
    )

    args = parser.parse_args()
    manager = MetadataManager(provider=create_provider(args.provider))

    if args.command == 'refresh':
        try:
            manager.refresh(strict=args.strict)
        except MetadataValidationError as exc:
            print(f'[FAIL] {exc}', file=sys.stderr)
            sys.exit(1)

    elif args.command == 'load':
        df = manager.load()
        print(df.head())


if __name__ == '__main__':
    main()
