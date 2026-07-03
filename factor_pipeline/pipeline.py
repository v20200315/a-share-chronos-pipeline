from __future__ import annotations

import argparse
from pathlib import Path

from factor_pipeline.engine import FactorEngine
from factor_pipeline.paths import FACTOR_OUTPUT_DIR, MARKET_DATA_SNAPSHOT_LATEST


def main() -> None:
    """Run the factor pipeline for one symbol."""
    parser = argparse.ArgumentParser(description='Run the factor pipeline for one symbol.')
    parser.add_argument('symbol', help='stock code, for example 600000')
    parser.add_argument(
        '--snapshot-dir',
        default=str(MARKET_DATA_SNAPSHOT_LATEST),
        help='market data snapshot directory',
    )
    parser.add_argument(
        '--daily-bars-dir',
        help='optional daily bars directory, used when no snapshot has been published yet',
    )
    parser.add_argument(
        '--output-dir',
        default=str(FACTOR_OUTPUT_DIR),
        help='factor parquet output directory',
    )
    args = parser.parse_args()

    engine = FactorEngine(
        snapshot_dir=Path(args.snapshot_dir),
        daily_bars_dir=Path(args.daily_bars_dir) if args.daily_bars_dir else None,
        output_dir=Path(args.output_dir),
    )
    result = engine.run(args.symbol)
    print(f'[OK] saved -> {result.output_path}')


if __name__ == '__main__':
    main()
