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
    ) -> None:
        """Initialize the engine.

        Args:
            snapshot_dir: Market-data snapshot directory containing ``manifest.json``.
            output_dir: Directory that stores exported factor parquet files.
        """
        self.snapshot = load_snapshot(snapshot_dir)
        self.output_dir = validate_output_dir(output_dir)

    def run(self, symbol: str) -> FactorEngineResult:
        """Execute the factor pipeline for one symbol.

        Args:
            symbol: Stock code, for example ``"600000"``.

        Returns:
            Metadata describing the exported factor dataset path.
        """
        df = load_market_data(symbol, snapshot=self.snapshot)
        df = clean(df)
        df = compute_technical_factors(df)
        df = compute_price_factors(df)
        df = compute_volume_factors(df)
        df = compute_volatility_factors(df)
        df = generate_labels(df)
        df = build_dataset(df)
        df = scale_dataset(df)
        output_path = export_factor_dataset(df, symbol, output_dir=self.output_dir)
        return FactorEngineResult(symbol=str(symbol).zfill(6), output_path=output_path)

    def run_all(self) -> FactorEngineBatchResult:
        """Execute the factor pipeline for every symbol listed in the snapshot manifest.

        Returns:
            Metadata describing all exported factor dataset paths.
        """
        saved_paths = [self.run(symbol).output_path for symbol in self.snapshot.symbols]
        return FactorEngineBatchResult(
            snapshot_dir=self.snapshot.snapshot_dir,
            saved_paths=saved_paths,
        )
