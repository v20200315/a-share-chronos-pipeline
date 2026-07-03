# Factor Pipeline

Skeleton pipeline that loads market data, runs placeholder factor stages, and
exports one factor parquet file per symbol.

## Run

```bash
python -m factor_pipeline.pipeline 600000
```

Input defaults to `market_data_pipeline/output/{symbol}.parquet`.
Output is written to `factor_pipeline/output/{symbol}_factor.parquet`.
