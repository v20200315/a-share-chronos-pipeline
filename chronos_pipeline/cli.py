import argparse
import sys

from chronos_pipeline.metadata.manager import MetadataManager
from chronos_pipeline.metadata.validator import MetadataValidationError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['refresh', 'load'])
    parser.add_argument(
        '--strict',
        action='store_true',
        help='treat validation warnings as errors',
    )

    args = parser.parse_args()
    manager = MetadataManager()

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
