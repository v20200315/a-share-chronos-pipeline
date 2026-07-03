from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factor_pipeline.cleaner.cleaner import clean
from factor_pipeline.dataset.builder import build_dataset
from factor_pipeline.dataset.scaler import scale_dataset
from factor_pipeline.factors.price import compute_price_factors
from factor_pipeline.factors.technical import compute_technical_factors
from factor_pipeline.factors.volatility import compute_volatility_factors
from factor_pipeline.factors.volume import compute_volume_factors
from factor_pipeline.io.exporter import export_factor_dataset
from factor_pipeline.io.loader import load_market_data
from factor_pipeline.labels.label_generator import generate_labels
from factor_pipeline.paths import FACTOR_OUTPUT_DIR, MARKET_DATA_INPUT_DIR


@dataclass(frozen=True)
class FactorEngineResult:
    """Result of a single-symbol factor-pipeline run."""

    symbol: str
    output_path: Path


class FactorEngine:
    """Orchestrate factor-pipeline stages for one symbol."""

    def __init__(
        self,
        *,
        input_dir: str | Path = MARKET_DATA_INPUT_DIR,
        output_dir: str | Path = FACTOR_OUTPUT_DIR,
    ) -> None:
        """Initialize the engine.

        Args:
            input_dir: Directory containing market-data parquet files.
            output_dir: Directory that stores exported factor parquet files.
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

    def run(self, symbol: str) -> FactorEngineResult:
        """Execute the factor pipeline for one symbol.

        Args:
            symbol: Stock code, for example ``"600000"``.

        Returns:
            Metadata describing the exported factor dataset path.
        """
        df = load_market_data(symbol, input_dir=self.input_dir)
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
