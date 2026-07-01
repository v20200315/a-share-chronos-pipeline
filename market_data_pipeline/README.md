# Market Data Pipeline

## English Version

### Overview

`market_data_pipeline` is responsible for building the raw market data layer used by downstream pipelines.
It currently supports stock metadata ingestion, metadata validation and cleanup, daily candlestick refresh, failed-symbol retries, and snapshot publishing.

Run the implemented market data CLI from the repository root with `python -m market_data_pipeline.cli`.

### Data Layout

The pipeline owns raw market data outputs under `data/market_data/`.
Downstream pipelines should consume `data/market_data/snapshots/latest/` as the stable input contract.

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
```

### Metadata CLI

The metadata workflow has separate steps:

1. Fetch raw provider data and save it to parquet.
2. Validate the saved parquet and generate a validation report.
3. If needed, preview and remove row-level errors from the parquet.
4. Validate again after cleanup.

Supported providers:

- `akshare`
- `eastmoney`

#### 1. Fetch Metadata

Fetch downloads data from the selected provider and saves it without validation.

```bash
python -m market_data_pipeline.cli refresh --provider akshare
python -m market_data_pipeline.cli refresh --provider eastmoney
```

Output files:

- `data/market_data/metadata/provider=akshare/stock_basic.parquet`
- `data/market_data/metadata/provider=eastmoney/stock_basic.parquet`

#### 2. Validate Metadata

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

#### 3. Preview Cleanup

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

#### 4. Apply Cleanup

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

#### 5. Load Metadata

Print the first rows of the saved parquet:

```bash
python -m market_data_pipeline.cli load --provider akshare
python -m market_data_pipeline.cli load --provider eastmoney
```

### Daily Candlestick CLI

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

#### Retry Failed Daily Refresh Symbols

If a daily refresh report has `failed_count > 0`, retry only the `failed_codes` from that report instead of fetching all symbols again. This keeps successful parquet files intact and reduces provider load.

```bash
export REPORT="data/market_data/audit/daily_bars/provider=akshare/<timestamp>_daily_refresh.json"

FAILED=$(python - <<'PY'
import json
import os
from pathlib import Path

report = json.loads(Path(os.environ["REPORT"]).read_text(encoding="utf-8"))
print(",".join(report["failed_codes"]))
PY
)

python -m market_data_pipeline.cli daily-refresh \
  --metadata-provider akshare \
  --symbols "$FAILED" \
  --max-concurrency 2
```

If the retry still fails with proxy or provider errors, wait for the network/provider to recover and rerun the same retry command.

### Market Data Snapshot

Publish a market-data snapshot after metadata and daily bars are refreshed:

```bash
python -m market_data_pipeline.cli publish-snapshot --metadata-provider akshare
```

This writes a timestamped snapshot and refreshes `data/market_data/snapshots/latest/`.
The snapshot contains `manifest.json`, `stock_basic.parquet`, and `daily_bars/<code>.parquet`.
`feature_pipeline` should read from `data/market_data/snapshots/latest/` instead of provider-specific working directories.

## 中文版本

**A股时序量化数据蓄水池工程**

### 概览

`market_data_pipeline` 负责构建下游流水线使用的原始行情数据层。
它目前支持股票元数据采集、元数据校验与清理、日线 K 线刷新、失败股票重试，以及行情数据快照发布。

在仓库根目录运行已实现的行情数据 CLI：`python -m market_data_pipeline.cli`。

### 数据目录结构

该流水线拥有 `data/market_data/` 下的原始行情数据输出。
下游流水线应该把 `data/market_data/snapshots/latest/` 作为稳定输入契约。

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
```

### 元数据 CLI

元数据流程分为几个独立步骤：

1. 拉取原始 provider 数据并保存为 parquet。
2. 校验已保存的 parquet，并生成校验报告。
3. 如有需要，先预览再清理 parquet 中的行级错误。
4. 清理后再次校验。

支持的 provider：

- `akshare`
- `eastmoney`

#### 1. 拉取元数据

`refresh` 会从指定 provider 下载数据，并在不做校验的情况下保存。

```bash
python -m market_data_pipeline.cli refresh --provider akshare
python -m market_data_pipeline.cli refresh --provider eastmoney
```

输出文件：

- `data/market_data/metadata/provider=akshare/stock_basic.parquet`
- `data/market_data/metadata/provider=eastmoney/stock_basic.parquet`

#### 2. 校验元数据

`validate` 会校验已保存的 parquet，并写入校验报告。

```bash
python -m market_data_pipeline.cli validate --provider akshare
python -m market_data_pipeline.cli validate --provider eastmoney
```

校验报告写入：

```text
data/market_data/audit/metadata/provider=<provider>/
```

如果希望 warning 也导致校验失败，可以使用 strict 模式：

```bash
python -m market_data_pipeline.cli validate --provider akshare --strict
python -m market_data_pipeline.cli validate --provider eastmoney --strict
```

#### 3. 预览清理结果

先使用 dry-run 模式运行清理。它会显示将删除多少行，但不会修改 parquet 文件。

```bash
python -m market_data_pipeline.cli clean --provider akshare --dry-run
python -m market_data_pipeline.cli clean --provider eastmoney --dry-run
```

如果 warning 级别的行问题也要删除，例如缺失 `list_date`，可以加上 `--strict`。

```bash
python -m market_data_pipeline.cli clean --provider akshare --strict --dry-run
python -m market_data_pipeline.cli clean --provider eastmoney --strict --dry-run
```

示例输出：

```text
[INFO] cleanup: before=5532, after=5531, removed=1
[INFO] removed codes: 600519
[INFO] dry-run: parquet not modified
```

#### 4. 应用清理

如果 dry-run 结果符合预期，去掉 `--dry-run` 后执行清理。

```bash
python -m market_data_pipeline.cli clean --provider akshare
python -m market_data_pipeline.cli clean --provider eastmoney
```

只有在明确希望删除 warning 级别行问题时，才使用 strict 清理。

```bash
python -m market_data_pipeline.cli clean --provider akshare --strict
python -m market_data_pipeline.cli clean --provider eastmoney --strict
```

清理会删除这些行级校验错误：

- 股票代码重复
- `code` 或 `name` 为空
- 股票代码不是合法的 6 位格式
- `exchange` 非法
- 交易所与代码前缀不匹配
- `list_date` 是未来日期

strict 清理还会删除 warning 级别行问题，例如缺失或无法解析的 `list_date`。

清理后再次校验：

```bash
python -m market_data_pipeline.cli validate --provider akshare
python -m market_data_pipeline.cli validate --provider eastmoney
```

#### 5. 读取元数据

打印已保存 parquet 的前几行：

```bash
python -m market_data_pipeline.cli load --provider akshare
python -m market_data_pipeline.cli load --provider eastmoney
```

### 日线 K 线 CLI

日线 K 线数据只使用 AKShare `stock_zh_a_hist`，并使用 `adjust='qfq'` 前复权。
股票池来自已保存的元数据 parquet。

为 AkShare 元数据 parquet 中的全部股票拉取前复权日线：

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare
```

日线刷新使用有界 asyncio 并发调用 AKShare。建议先用较低并发开始，如果 provider 稳定再提高：

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare --max-concurrency 8
```

也可以使用另一个元数据 parquet 作为股票池，但日线数据仍然来自 AKShare：

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider eastmoney
```

测试时可以只拉取少量股票：

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare --symbols 600519,000001
```

也可以只拉取元数据过滤排序后的前 N 只股票：

```bash
python -m market_data_pipeline.cli daily-refresh --metadata-provider akshare --top 100
```

每只股票会保存为独立 parquet 文件：

```text
data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d/<code>.parquet
```

每次运行也会写入本地 JSON 报告，记录成功、跳过、失败数量：

```text
data/market_data/audit/daily_bars/provider=akshare/<timestamp>_daily_refresh.json
```

每只股票的拉取窗口：

- `end_date`：今天
- `start_date`：默认 5 年前
- 如果股票上市时间不足 5 年，`start_date` 使用该股票的 `list_date`

`list_date` 非法的行会被跳过，因为无法安全确定拉取窗口。

只有当返回数据的 `date` 范围覆盖请求窗口端点时，才会写入日线 parquet；周末和节假日允许 7 天容忍。空数据、无法解析日期、起点过晚、终点过早的数据都会标记为失败，不会写入 parquet。

#### 从报告重试失败股票

如果日线刷新报告中 `failed_count > 0`，只重试报告里的 `failed_codes`，不要重新拉取全部股票。这样可以保留已经成功写入的 parquet 文件，并减少 provider 压力。

```bash
export REPORT="data/market_data/audit/daily_bars/provider=akshare/<timestamp>_daily_refresh.json"

FAILED=$(python - <<'PY'
import json
import os
from pathlib import Path

report = json.loads(Path(os.environ["REPORT"]).read_text(encoding="utf-8"))
print(",".join(report["failed_codes"]))
PY
)

python -m market_data_pipeline.cli daily-refresh \
  --metadata-provider akshare \
  --symbols "$FAILED" \
  --max-concurrency 2
```

如果重试仍然出现代理或 provider 错误，先等待网络或 provider 恢复，再执行同一条重试命令。

### 行情数据快照

元数据和日线数据刷新完成后，发布行情数据快照：

```bash
python -m market_data_pipeline.cli publish-snapshot --metadata-provider akshare
```

该命令会写入一个带时间戳的快照，并刷新 `data/market_data/snapshots/latest/`。
快照包含 `manifest.json`、`stock_basic.parquet` 和 `daily_bars/<code>.parquet`。
`feature_pipeline` 应该读取 `data/market_data/snapshots/latest/`，而不是直接读取 provider 相关的工作目录。