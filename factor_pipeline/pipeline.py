from __future__ import annotations

import argparse
from pathlib import Path

from factor_pipeline.engine import FactorEngine
from factor_pipeline.paths import FACTOR_OUTPUT_DIR, MARKET_DATA_INPUT_DIR


def main() -> None:
    """Run the factor pipeline for one symbol."""
    parser = argparse.ArgumentParser(description='Run the factor pipeline for one symbol.')
    parser.add_argument('symbol', help='stock code, for example 600000')
    parser.add_argument(
        '--input-dir',
        default=str(MARKET_DATA_INPUT_DIR),
        help='market data parquet input directory',
    )
    parser.add_argument(
        '--output-dir',
        default=str(FACTOR_OUTPUT_DIR),
        help='factor parquet output directory',
    )
    args = parser.parse_args()

    engine = FactorEngine(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
    )
    result = engine.run(args.symbol)
    print(f'[OK] saved -> {result.output_path}')


if __name__ == '__main__':
    main()
