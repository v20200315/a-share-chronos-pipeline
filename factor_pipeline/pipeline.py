from __future__ import annotations

import argparse
import sys

from factor_pipeline.engine import FactorEngine
from factor_pipeline.paths import FACTOR_OUTPUT_DIR, MARKET_DATA_SNAPSHOT_LATEST


def main() -> None:
    """Run the factor pipeline for all symbols listed in a snapshot manifest."""
    parser = argparse.ArgumentParser(description='Run the factor pipeline.')
    parser.add_argument(
        '--snapshot-dir',
        default=str(MARKET_DATA_SNAPSHOT_LATEST),
        help='market data snapshot directory containing manifest.json',
    )
    parser.add_argument(
        '--output-dir',
        default=str(FACTOR_OUTPUT_DIR),
        help='directory that stores exported factor parquet files',
    )
    args = parser.parse_args()

    try:
        engine = FactorEngine(
            snapshot_dir=args.snapshot_dir,
            output_dir=args.output_dir,
        )
        result = engine.run_all()
    except (FileNotFoundError, ValueError) as exc:
        print(f'[FAIL] {exc}', file=sys.stderr)
        sys.exit(1)

    for saved_path in result.saved_paths:
        print(f'[OK] saved -> {saved_path}')


if __name__ == '__main__':
    main()
