# A-Share Chronos Pipeline 
# A股时序量化数据蓄水池工程

## Sub-Pipelines

The project is organized into four top-level pipeline packages:

- `market_data_pipeline`: implemented market data ingestion, metadata validation, and daily candlestick refresh.
- `feature_pipeline`: feature engineering package placeholder.
- `model_pipeline`: model training and inference package placeholder.
- `backtest_pipeline`: backtesting package placeholder.

Run the implemented market data CLI from the repository root with `python -m market_data_pipeline.cli`.

## Data Layout

`market_data_pipeline` owns raw market data outputs under `data/market_data/`.
`feature_pipeline` should consume `data/market_data/snapshots/latest/` as its stable input contract.

```text
data/
  market_data/
    metadata/
      provider=akshare/stock_basic.parquet
      provider=eastmoney/stock_basic.parquet
    daily_bars/
      provider=akshare/adjust=qfq/frequency=1d/<code>.parquet
    snapshots/
      latest/
        manifest.json
        stock_basic.parquet
        daily_bars/<code>.parquet
    audit/
      metadata/provider=<provider>/
      daily_bars/provider=akshare/
  features/
    <feature_set>/version=<version>/
```

## Metadata CLI

The metadata workflow has separate steps:

1. Fetch raw provider data and save it to parquet.
2. Validate the saved parquet and generate a validation report.
3. If needed, preview and remove row-level errors from the parquet.
4. Validate again after cleanup.

Supported providers:

- `akshare`
- `eastmoney`

### 1. Fetch Metadata

Fetch downloads data from the selected provider and saves it without validation.

```bash
python -m market_data_pipeline.cli refresh --provider akshare
python -m market_data_pipeline.cli refresh --provider eastmoney
```

Output files:

- `data/market_data/metadata/provider=akshare/stock_basic.parquet`
- `data/market_data/metadata/provider=eastmoney/stock_basic.parquet`

### 2. Validate Metadata

Validate checks the saved parquet and writes a validation report.

```bash
python -m market_data_pipeline.cli validate --provider akshare
python -m market_data_pipeline.cli validate --provider eastmoney
```

Validation reports are written under:

```text
data/market_data/audit/metadata/provider=<provider>/
```

Use strict mode if warnings should fail validation:

```bash
python -m market_data_pipeline.cli validate --provider akshare --strict
python -m market_data_pipeline.cli validate --provider eastmoney --strict
```

### 3. Preview Cleanup

Run cleanup in dry-run mode first. This shows how many rows would be removed, but does not modify the parquet file.

```bash
python -m market_data_pipeline.cli clean --provider akshare --dry-run
python -m market_data_pipeline.cli clean --provider eastmoney --dry-run
```

Add `--strict` if warning-level row issues should also be removed, such as missing `list_date`.

```bash
python -m market_data_pipeline.cli clean --provider akshare --strict --dry-run
python -m market_data_pipeline.cli clean --provider eastmoney --strict --dry-run
```

Example output:

```text
[INFO] cleanup: before=5532, after=5531, removed=1
[INFO] removed codes: 600519
[INFO] dry-run: parquet not modified
```

### 4. Apply Cleanup

If the dry-run result looks correct, run cleanup without `--dry-run`.

```bash
python -m market_data_pipeline.cli clean --provider akshare
python -m market_data_pipeline.cli clean --provider eastmoney
```

Use strict cleanup only when you intentionally want to remove warning-level row issues.

```bash
python -m market_data_pipeline.cli clean --provider akshare --strict
python -m market_data_pipeline.cli clean --provider eastmoney --strict
```

Cleanup removes row-level validation errors such as:

- duplicate stock codes
- null `code` or `name`
- invalid 6-digit stock code format
- invalid `exchange`
- exchange/code prefix mismatch
- future `list_date`

Strict cleanup also removes warning-level row issues, such as missing or unparsable `list_date`.

After cleanup, validate again:

```bash
python -m market_data_pipeline.cli validate --provider akshare
python -m market_data_pipeline.cli validate --provider eastmoney
```

### 5. Load Metadata

Print the first rows of the saved parquet:

```bash
python -m market_data_pipeline.cli load --provider akshare
python -m market_data_pipeline.cli load --provider eastmoney
```

## Daily Candlestick CLI

Daily candlestick data uses AKShare `stock_zh_a_hist` only, with `adjust='qfq'`.
The stock universe comes from the saved metadata parquet.

Fetch qfq daily bars for every stock in the AkShare metadata parquet:

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare
```

Daily refresh uses bounded asyncio concurrency around AKShare requests. Start with a modest concurrency value, then increase only if the provider remains stable:

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare --max-concurrency 8
```

Use another metadata parquet as the stock universe, while still using AKShare for daily bars:

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider eastmoney
```

Fetch a small set of symbols for testing:

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare --symbols 600519,000001
```

Fetch only the first N stocks from the metadata parquet:

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare --top 100
```

Each stock is saved as its own parquet file:

```text
data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d/<code>.parquet
```

Each run also writes a local JSON report with success, skipped, and failed counts:

```text
data/market_data/audit/daily_bars/provider=akshare/<timestamp>_daily_refresh.json
```

For each stock, the fetch window is:

- `end_date`: today
- `start_date`: 5 years ago, unless the stock listed more recently
- if listed less than 5 years ago, `start_date` is the stock's `list_date`

Rows with invalid `list_date` are skipped because the fetch window cannot be bounded safely.

Fetched daily bars are saved only when the returned `date` range covers the requested window endpoints, with a 7-day tolerance for weekends and holidays. Empty, unparsable, late-starting, or early-ending results are marked as failed and are not written to parquet.

## Market Data Snapshot

Publish a market-data snapshot after metadata and daily bars are refreshed:

```bash
python -m market_data_pipeline.cli publish-snapshot --metadata-provider akshare
```

This writes a timestamped snapshot and refreshes `data/market_data/snapshots/latest/`.
The snapshot contains `manifest.json`, `stock_basic.parquet`, and `daily_bars/<code>.parquet`.
`feature_pipeline` should read from `data/market_data/snapshots/latest/` instead of provider-specific working directories.