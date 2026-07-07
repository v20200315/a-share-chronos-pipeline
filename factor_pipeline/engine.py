from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from factor_pipeline.cleaner.cleaner import clean
from factor_pipeline.dataset.builder import build_dataset
from factor_pipeline.dataset.scaler import scale_dataset
from factor_pipeline.factors.price import compute_price_factors
from factor_pipeline.factors.technical import compute_technical_factors
from factor_pipeline.factors.volatility import compute_volatility_factors
from factor_pipeline.factors.volume import compute_volume_factors
from factor_pipeline.io.exporter import export_factor_dataset
from factor_pipeline.io.loader import load_market_data, load_snapshot
from factor_pipeline.labels.label_generator import generate_labels
from factor_pipeline.paths import (
    FACTOR_OUTPUT_DIR,
    MARKET_DATA_SNAPSHOT_LATEST,
    validate_output_dir,
)


@dataclass(frozen=True)
class FactorEngineResult:
    """Result of a single-symbol factor-pipeline run."""

    symbol: str
    output_path: Path


@dataclass(frozen=True)
class FactorEngineBatchResult:
    """Result of a multi-symbol factor-pipeline run."""

    snapshot_dir: Path
    saved_paths: list[Path] = field(default_factory=list)


class FactorEngine:
    """Orchestrate factor-pipeline stages using snapshot manifest metadata."""

    def __init__(
        self,
        *,
        snapshot_dir: str | Path = MARKET_DATA_SNAPSHOT_LATEST,
        output_dir: str | Path = FACTOR_OUTPUT_DIR,
        verbose: bool = False,
    ) -> None:
        """Initialize the engine.

        Args:
            snapshot_dir: Market-data snapshot directory containing ``manifest.json``.
            output_dir: Directory that stores exported factor parquet files.
            verbose: Print pipeline step messages to stdout when ``True``.
        """
        self.verbose = verbose
        self.snapshot = load_snapshot(snapshot_dir)
        self.output_dir = validate_output_dir(output_dir)
        if self.verbose:
            _print_step(f'snapshot -> {self.snapshot.snapshot_dir}')
            _print_step(f'daily bars -> {self.snapshot.daily_bars_dir}')
            _print_step(f'symbols -> {", ".join(self.snapshot.symbols)}')
            _print_step(f'output -> {self.output_dir}')

    def run(self, symbol: str) -> FactorEngineResult:
        """Execute the factor pipeline for one symbol.

        Args:
            symbol: Stock code, for example ``"600000"``.

        Returns:
            Metadata describing the exported factor dataset path.
        """
        normalized_symbol = str(symbol).zfill(6)
        if self.verbose:
            _print_step(f'[{normalized_symbol}] load market data')

        df = load_market_data(symbol, snapshot=self.snapshot)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] clean data')
        df = clean(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] compute technical factors')
        df = compute_technical_factors(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] compute price factors')
        df = compute_price_factors(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] compute volume factors')
        df = compute_volume_factors(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] compute volatility factors')
        df = compute_volatility_factors(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] generate labels')
        df = generate_labels(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] build dataset')
        df = build_dataset(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] scale dataset')
        df = scale_dataset(df)

        if self.verbose:
            _print_step(f'[{normalized_symbol}] export parquet')
        output_path = export_factor_dataset(df, symbol, output_dir=self.output_dir)
        return FactorEngineResult(symbol=normalized_symbol, output_path=output_path)

    def run_all(self) -> FactorEngineBatchResult:
        """Execute the factor pipeline for every symbol listed in the snapshot manifest.

        Returns:
            Metadata describing all exported factor dataset paths.
        """
        symbols = self.snapshot.symbols
        saved_paths: list[Path] = []
        for index, symbol in enumerate(symbols, start=1):
            if self.verbose:
                _print_step(f'processing symbol {symbol} ({index}/{len(symbols)})')
            saved_paths.append(self.run(symbol).output_path)
        return FactorEngineBatchResult(
            snapshot_dir=self.snapshot.snapshot_dir,
            saved_paths=saved_paths,
        )


def _print_step(message: str) -> None:
    print(f'[INFO] {message}')
