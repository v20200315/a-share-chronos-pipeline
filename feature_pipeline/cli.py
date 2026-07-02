from __future__ import annotations

import argparse
from pathlib import Path

from feature_pipeline.manager import FeatureManager


def parse_symbols(value: str) -> list[str]:
    return [symbol.strip().zfill(6) for symbol in value.split(',') if symbol.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['compute'])
    parser.add_argument(
        '--symbols',
        required=True,
        help='comma-separated stock codes, for example 000001,600000',
    )
    parser.add_argument(
        '--snapshot-dir',
        default='data/market_data/snapshots/latest',
        help='market data snapshot directory',
    )
    parser.add_argument(
        '--daily-bars-dir',
        help='optional daily bars directory, used when no snapshot has been published yet',
    )
    parser.add_argument(
        '--output-dir',
        default='data/features/technical_indicators/version=v1',
        help='feature parquet output directory',
    )

    args = parser.parse_args()
    manager = FeatureManager(
        snapshot_dir=Path(args.snapshot_dir),
        daily_bars_dir=Path(args.daily_bars_dir) if args.daily_bars_dir else None,
        output_dir=Path(args.output_dir),
    )
    result = manager.compute(symbols=parse_symbols(args.symbols))
    for saved_path in result.saved_paths:
        print(f'[OK] saved -> {saved_path}')


if __name__ == '__main__':
    main()
