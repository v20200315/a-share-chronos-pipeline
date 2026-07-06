from __future__ import annotations

import argparse
import sys
from pathlib import Path

from factor_pipeline.engine import FactorEngine
from factor_pipeline.paths import FACTOR_INPUT_DIR, FACTOR_OUTPUT_DIR


def main() -> None:
    """Run the factor pipeline for all symbols in the input directory."""
    parser = argparse.ArgumentParser(description='Run the factor pipeline.')
    parser.add_argument(
        '--input-dir',
        default=str(FACTOR_INPUT_DIR),
        help='directory containing one parquet file per symbol, for example daily_bars/',
    )
    parser.add_argument(
        '--output-dir',
        default=str(FACTOR_OUTPUT_DIR),
        help='directory that stores exported factor parquet files',
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    if not input_dir.is_dir():
        print(f'[FAIL] input directory not found: {input_dir}', file=sys.stderr)
        sys.exit(1)

    parquet_files = sorted(input_dir.glob('*.parquet'))
    if not parquet_files:
        print(f'[FAIL] no parquet files found in: {input_dir}', file=sys.stderr)
        sys.exit(1)

    engine = FactorEngine(daily_bars_dir=input_dir, output_dir=output_dir)
    for parquet_path in parquet_files:
        result = engine.run(parquet_path.stem)
        print(f'[OK] saved -> {result.output_path}')


if __name__ == '__main__':
    main()
