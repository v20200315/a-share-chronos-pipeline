# Factor Pipeline / 因子流水线

---

## English

### Overview

`factor_pipeline` is the second layer in the A-share quantitative research stack. It consumes daily market data published by `market_data_pipeline` and produces per-symbol factor datasets for downstream `alpha_model_pipeline` and `backtest_pipeline`.

The pipeline is **wired end-to-end**. Input loading, snapshot validation, output-directory checks, the **data quality layer** (`cleaner/`), all **factor stages** (`technical.py`, `price.py`, `volume.py`, `volatility.py`), and **label generation** (`labels/label_generator.py` — forward return + binary label) are implemented. Dataset build/scale stages remain placeholders until real logic is added.

```
market_data_pipeline
        │
        ▼
factor_pipeline          ← you are here
        │
        ▼
alpha_model_pipeline
        │
        ▼
backtest_pipeline
```

### Directory Layout

```
factor_pipeline/
├── __init__.py              # Package entry; exports FactorEngine, FactorEngineResult
├── paths.py                 # Default path constants and output-dir validation
├── engine.py                # Orchestrates all stages in order
├── pipeline.py              # CLI entry point (--snapshot-dir, --output-dir)
├── README.md
│
├── io/
│   ├── __init__.py          # Re-exports loader and exporter public APIs
│   ├── loader.py            # Load snapshot manifest and one symbol parquet
│   └── exporter.py          # Write factor parquet to output directory
│
├── cleaner/
│   ├── __init__.py
│   └── cleaner.py           # OHLCV validation and standardization (MarketDataCleaner)
│
├── factors/
│   ├── __init__.py
│   ├── base.py              # Shared pass-through helper for factor stages
│   ├── technical.py         # Technical factors: MACD + RSI (TechnicalFactorGenerator)
│   ├── price.py             # Price factors: returns + momentum (PriceFactorGenerator)
│   ├── volume.py            # Volume factors: change + MA + ratio + turnover (VolumeFactorGenerator)
│   └── volatility.py        # Volatility factors: rolling std + hist vol + ATR (VolatilityFactorGenerator)
│
├── labels/
│   ├── __init__.py
│   └── label_generator.py   # Labels: future_return + binary label (LabelGenerator)
│
├── dataset/
│   ├── __init__.py
│   ├── builder.py           # Dataset assembly stage (placeholder)
│   ├── scaler.py            # Feature scaling stage (placeholder)
│   └── splitter.py          # Train/validation/test split (placeholder, not wired yet)
│
└── (output written to data/factor_pipeline/output/)
    └── {symbol}_factor.parquet
```

### File Responsibilities

| File | Responsibility | Current Behavior |
|------|----------------|------------------|
| `paths.py` | Default paths | `MARKET_DATA_SNAPSHOT_LATEST`, `FACTOR_OUTPUT_DIR`, `validate_output_dir()` |
| `io/loader.py` | Read market data | Loads `manifest.json`, validates snapshot paths and symbols, reads `{symbol}.parquet` via PyArrow, validates required columns, returns raw DataFrame |
| `io/exporter.py` | Persist factor output | Writes `data/factor_pipeline/output/{symbol}_factor.parquet` |
| `cleaner/cleaner.py` | Data quality layer | `MarketDataCleaner`: standardize dates, sort, dedupe, validate OHLCV rules (see below) |
| `factors/technical.py` | Technical factors | `TechnicalFactorGenerator`: MACD (12/26/9) and RSI (14) via TA-Lib; appends `macd`, `macd_signal`, `macd_hist`, `rsi` |
| `factors/price.py` | Price factors | `PriceFactorGenerator`: daily returns and momentum from `close`; appends `return_1d`, `return_5d`, `return_10d`, `momentum_5d`, `momentum_10d` |
| `factors/volume.py` | Volume factors | `VolumeFactorGenerator`: volume change, MA, ratio, and turnover from `volume`/`turnover`; appends 7 columns (see below) |
| `factors/volatility.py` | Volatility factors | `VolatilityFactorGenerator`: rolling return std, annualized historical vol, ATR from `high`/`low`/`close`; appends 4 columns (see below) |
| `labels/label_generator.py` | Supervised labels | `LabelGenerator`: forward return and binary `label` from `close`; drops last `horizon` rows (default 5) |
| `dataset/*.py` | Dataset prep | Pass-through placeholders; `splitter.py` not wired into `engine.py` |
| `engine.py` | Pipeline orchestration | Loads snapshot, validates output dir, runs all active stages per symbol |
| `pipeline.py` | Program entry point | Parses `--snapshot-dir` and `--output-dir`, runs `FactorEngine.run_all()` |

### Validation Layers

| Layer | Module | What it checks |
|-------|--------|----------------|
| Snapshot input | `io/loader.py` | `snapshot_dir` exists, `manifest.json`, `daily_bars_path`, `metadata_path`, non-empty `symbols`, per-symbol parquet exists |
| Row schema | `io/loader.py` | Required columns present in parquet schema |
| Data quality | `cleaner/cleaner.py` | Date standardization, sort, dedupe, OHLCV business rules on row values |
| Output path | `engine.py` via `paths.validate_output_dir()` | Output directory creatable and writable before processing |

### Input Contract

Data is read from the published market-data snapshot:

```
data/market_data/snapshots/latest/
├── manifest.json
├── stock_basic.parquet
└── daily_bars/
    ├── 000001.parquet
    └── 600000.parquet
```

`loader.py` reads `manifest.json` and resolves `daily_bars_path`. Each daily-bar parquet must contain:

```
date, code, open, high, low, close, volume, amount, amplitude, pct_change, change, turnover
```

The loader returns the DataFrame **as stored** — no sorting, normalization, or enrichment.

### Data Quality Rules (`cleaner/cleaner.py`)

After `loader.py` returns raw parquet data, `MarketDataCleaner` standardizes and validates each symbol DataFrame.

#### Standardization (always applied)

| Step | Rule |
|------|------|
| Date | Convert `date` to `datetime64` (`pd.to_datetime`, invalid dates raise) |
| Sort | Sort rows by `date` ascending |
| Dedupe | Drop duplicate `(code, date)` rows, keep first occurrence |

#### Schema check

All loader columns must be present. Missing columns raise `ValueError`.

#### OHLCV business rules

Rules are checked **only on non-NaN values** (NaN cells are skipped, not filled).

| Rule | Condition | Applies when |
|------|-----------|--------------|
| High bound | `high >= max(open, close)` | `open`, `high`, `close` are all non-null |
| Low bound | `low <= min(open, close)` | `open`, `low`, `close` are all non-null |
| Range | `high >= low` | `high`, `low` are both non-null |
| Price | `close > 0` | `close` is non-null |
| Volume | `volume >= 0` | `volume` is non-null |
| Turnover | `turnover >= 0` | `turnover` is non-null |

Any violation raises `MarketDataValidationError` with the rule name, failure count, and up to 3 sample `(code, date)` rows.

#### Explicit non-goals

- Does **not** fill or impute NaN
- Does **not** add factor or label columns
- Does **not** scale or export data

### Technical Factors (`factors/technical.py`)

After cleaning, `TechnicalFactorGenerator` appends TA-Lib indicators from the `close` column. The input DataFrame is never mutated; all columns are added on a copy.

#### Output columns

| Column | Indicator | TA-Lib call | Parameters |
|--------|-----------|-------------|------------|
| `macd` | MACD line | `talib.MACD` | fastperiod=12, slowperiod=26, signalperiod=9 |
| `macd_signal` | MACD signal | `talib.MACD` | same |
| `macd_hist` | MACD histogram | `talib.MACD` | same |
| `rsi` | Relative Strength Index | `talib.RSI` | timeperiod=14 |

Leading `NaN` values from rolling windows are preserved (not filled).

#### Validation and errors

| Check | Behavior |
|-------|----------|
| Required input | `close` must exist; otherwise `ValueError` |
| No overwrite | Raises `ValueError` if any output column already exists |

#### Explicit non-goals

- Does **not** fill or impute indicator NaNs
- Does **not** modify original market-data columns

### Price Factors (`factors/price.py`)

After technical factors, `PriceFactorGenerator` appends price-derived columns from the `close` column using pandas vectorized operations. The input DataFrame is never mutated; all columns are added on a copy.

#### Output columns

| Column | Factor | Formula |
|--------|--------|---------|
| `return_1d` | 1-day return | `close / close.shift(1) - 1` |
| `return_5d` | 5-day return | `close / close.shift(5) - 1` |
| `return_10d` | 10-day return | `close / close.shift(10) - 1` |
| `momentum_5d` | 5-day momentum | `close - close.shift(5)` |
| `momentum_10d` | 10-day momentum | `close - close.shift(10)` |

Leading `NaN` values from `shift()` are preserved (not filled).

#### Validation and errors

| Check | Behavior |
|-------|----------|
| Required input | `close` must exist; otherwise `ValueError` |
| No overwrite | Raises `ValueError` if any output column already exists |

#### Explicit non-goals

- Does **not** fill or impute factor NaNs
- Does **not** modify original market-data or upstream factor columns

### Volume Factors (`factors/volume.py`)

After price factors, `VolumeFactorGenerator` appends volume- and liquidity-related columns from `volume` and `turnover` using pandas vectorized operations. The input DataFrame is never mutated; all columns are added on a copy.

#### Output columns

| Column | Factor | Formula |
|--------|--------|---------|
| `volume_change_1d` | 1-day volume change | `volume / volume.shift(1) - 1` |
| `volume_change_5d` | 5-day volume change | `volume / volume.shift(5) - 1` |
| `volume_ma_5` | 5-day volume MA | `volume.rolling(5).mean()` |
| `volume_ma_10` | 10-day volume MA | `volume.rolling(10).mean()` |
| `volume_ratio_5` | Volume vs 5-day MA | `volume / volume_ma_5` |
| `turnover_ma_5` | 5-day turnover MA | `turnover.rolling(5).mean()` |
| `turnover_change_1d` | 1-day turnover change | `turnover / turnover.shift(1) - 1` |

Leading `NaN` values from `shift()` and `rolling()` are preserved (not filled). `volume_ratio_5` depends on `volume_ma_5` computed in the same stage.

#### Validation and errors

| Check | Behavior |
|-------|----------|
| Required input | `volume` and `turnover` must exist; otherwise `ValueError` |
| No overwrite | Raises `ValueError` if any output column already exists |

#### Explicit non-goals

- Does **not** fill or impute factor NaNs
- Does **not** modify original market-data or upstream factor columns

### Volatility Factors (`factors/volatility.py`)

After volume factors, `VolatilityFactorGenerator` appends volatility-related columns from `high`, `low`, and `close`. Rolling metrics use pandas; ATR uses TA-Lib. The input DataFrame is never mutated; all columns are added on a copy.

#### Output columns

| Column | Factor | Formula / Source |
|--------|--------|------------------|
| `rolling_std_5` | 5-day return volatility | `close.pct_change().rolling(5).std()` |
| `rolling_std_10` | 10-day return volatility | `close.pct_change().rolling(10).std()` |
| `historical_volatility_20` | 20-day annualized vol | `close.pct_change().rolling(20).std() * sqrt(252)` |
| `atr_14` | Average True Range | `talib.ATR(high, low, close, timeperiod=14)` |

Leading `NaN` values from `rolling()` and TA-Lib warm-up are preserved (not filled).

#### Validation and errors

| Check | Behavior |
|-------|----------|
| Required input | `high`, `low`, and `close` must exist; otherwise `ValueError` |
| No overwrite | Raises `ValueError` if any output column already exists |

#### Explicit non-goals

- Does **not** fill or impute factor NaNs
- Does **not** modify original market-data or upstream factor columns

### Labels (`labels/label_generator.py`)

After all factor stages, `LabelGenerator` appends supervised-learning targets from `close`. The input DataFrame is never mutated on retained rows; label columns are added on a copy, then tail rows without a future price are removed.

#### Default parameters

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `horizon` | `5` | Forward return window in trading days |
| `threshold` | `0.02` | Minimum forward return for `label = 1` |

#### Output columns

| Column | Definition |
|--------|------------|
| `future_return` | `close.shift(-horizon) / close - 1` |
| `label` | `1` if `future_return >= threshold`, else `0` |

#### Tail-row removal

The last `horizon` rows have no observable future close. They are dropped before return so factor columns on each exported row contain no look-ahead bias. Output row count = input row count − `horizon` (default: −5).

#### Validation and errors

| Check | Behavior |
|-------|----------|
| Required input | `close` must exist; otherwise `ValueError` |
| No overwrite | Raises `ValueError` if `future_return` or `label` already exist |

#### Explicit non-goals

- Does **not** modify factor columns
- Does **not** scale features or split train/validation/test

### Output Contract

```
data/factor_pipeline/output/{symbol}_factor.parquet
```

Example: `data/factor_pipeline/output/600000_factor.parquet`

Current output columns = input market-data columns + all factor columns (20 total; see factor sections above) + `future_return` + `label`.

Output row count = cleaned market-data rows − `horizon` (default 5). Example: 1,211 daily bars → 1,206 exported rows per symbol.

### Full Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  pipeline.py  (CLI)                                             │
│  python -m factor_pipeline.pipeline --snapshot-dir ... --output-dir ... │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  engine.py  (FactorEngine.run)                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    ▼                        ▼                        ▼
 io/loader.py          cleaner/cleaner.py      factors/technical.py
 load_snapshot()        MarketDataCleaner       compute_technical_factors(df)
 load_market_data()     standardize + validate OHLCV
    │                        │                        ▼
    │                        │               factors/price.py → volume → volatility
    │                        │                        │
    │                        │                        ▼
    │                        │            labels/label_generator.py (generate_labels)
    │                        │                        │
    │                        │                        ▼
    │                        │               dataset/builder.py → scaler.py
    │                        │                        │
    └────────────────────────┴────────────────────────┘
                             │
                             ▼
                    io/exporter.py
                    export_factor_dataset(df, symbol)
                             │
                             ▼
              data/factor_pipeline/output/600000_factor.parquet
```

**Stage order in `engine.py`:**

1. Load Data — `load_snapshot()` + `load_market_data()`
2. Clean Data — `MarketDataCleaner.clean()`: datetime, sort, dedupe, OHLCV rules
3. Technical Factors — `compute_technical_factors()`
4. Price Factors — `compute_price_factors()`
5. Volume Factors — `compute_volume_factors()`
6. Volatility Factors — `compute_volatility_factors()`
7. Generate Labels — `generate_labels()`
8. Build Dataset — `build_dataset()`
9. Scale Dataset — `scale_dataset()`
10. Export Parquet — `export_factor_dataset()`

### Run

```bash
# Default: snapshot from data/market_data/snapshots/latest
#          output to data/factor_pipeline/output
python -m factor_pipeline.pipeline
```

```bash
python -m factor_pipeline.pipeline \
  --snapshot-dir data/market_data/snapshots/latest \
  --output-dir data/factor_pipeline/output
```

Expected stdout:

```
[OK] saved -> data/factor_pipeline/output/600000_factor.parquet
```

### Programmatic Usage

```python
from factor_pipeline.engine import FactorEngine

engine = FactorEngine()
result = engine.run('600000')
print(result.output_path)
```

### Tests

```bash
python -m pytest tests/test_factor_pipeline_loader.py tests/test_factor_pipeline_cleaner.py tests/test_factor_pipeline_technical.py tests/test_factor_pipeline_price.py tests/test_factor_pipeline_volume.py tests/test_factor_pipeline_volatility.py tests/test_factor_pipeline_label_generator.py -v
```

- `test_factor_pipeline_loader.py` — snapshot loading, path validation, exporter, end-to-end engine
- `test_factor_pipeline_cleaner.py` — date sort, dedupe, OHLCV rules, NaN skip policy
- `test_factor_pipeline_technical.py` — MACD/RSI vs TA-Lib reference, missing-column and overwrite guards
- `test_factor_pipeline_price.py` — returns/momentum formulas, NaN behavior, missing-column and overwrite guards
- `test_factor_pipeline_volume.py` — volume/turnover formulas, NaN behavior, missing-column and overwrite guards
- `test_factor_pipeline_volatility.py` — rolling std/hist vol formulas, ATR vs TA-Lib, NaN behavior, missing-column and overwrite guards
- `test_factor_pipeline_label_generator.py` — forward return, binary labels, horizon/threshold config, tail-row removal

### Design Notes

- Replaces the older `feature_pipeline` input contract (snapshot-based loading).
- Does **not** import `market_data_pipeline` directly.
- Does **not** implement scaling (RobustScaler) or ML.
- All four factor modules and `LabelGenerator` are implemented.
- `dataset/builder.py`, `dataset/scaler.py`, and `dataset/splitter.py` remain placeholders; `splitter.py` is not wired into `engine.py`.

---

## 中文

### 概述

`factor_pipeline` 是 A 股量化研究体系中的第二层。它读取 `market_data_pipeline` 发布的日频行情快照，为下游的 `alpha_model_pipeline` 和 `backtest_pipeline` 生成按股票代码拆分的因子数据集。

流水线已**端到端打通**。输入加载、快照校验、输出目录校验、**数据质量层**（`cleaner/`）、全部**因子阶段**（`technical.py`、`price.py`、`volume.py`、`volatility.py`）以及**标签生成**（`labels/label_generator.py` — 远期收益 + 二分类标签）已实现。数据集构建与缩放阶段仍为占位，待后续接入真实逻辑。

```
market_data_pipeline
        │
        ▼
factor_pipeline          ← 当前模块
        │
        ▼
alpha_model_pipeline
        │
        ▼
backtest_pipeline
```

### 目录结构

```
factor_pipeline/
├── __init__.py              # 包入口；导出 FactorEngine、FactorEngineResult
├── paths.py                 # 默认路径常量与输出目录校验
├── engine.py                # 按顺序编排所有阶段
├── pipeline.py              # CLI 入口（--snapshot-dir, --output-dir）
├── README.md
│
├── io/
│   ├── loader.py            # 读取快照 manifest 与单只股票 parquet
│   └── exporter.py          # 将因子数据写入输出目录
│
├── cleaner/
│   └── cleaner.py           # OHLCV 校验与标准化（MarketDataCleaner）
│
├── factors/
│   ├── technical.py         # 技术因子：MACD + RSI（TechnicalFactorGenerator）
│   ├── price.py             # 价格因子：收益率 + 动量（PriceFactorGenerator）
│   ├── volume.py            # 成交量因子：变化 + 均线 + 比率 + 换手率（VolumeFactorGenerator）
│   └── volatility.py        # 波动率因子：滚动标准差 + 历史波动率 + ATR（VolatilityFactorGenerator）
│
├── labels/
│   └── label_generator.py   # 标签：远期收益 + 二分类 label（LabelGenerator）
├── dataset/                 # 数据集阶段（占位，splitter 未接入 engine）
│
└── （输出目录：data/factor_pipeline/output/）
    └── {symbol}_factor.parquet
```

### 文件职责

| 文件 | 职责 | 当前行为 |
|------|------|----------|
| `paths.py` | 默认路径 | `MARKET_DATA_SNAPSHOT_LATEST`、`FACTOR_OUTPUT_DIR`、`validate_output_dir()` |
| `io/loader.py` | 读取行情 | 读取 manifest、校验快照路径与 symbols、加载 parquet、校验必需列，返回原始 DataFrame |
| `io/exporter.py` | 持久化输出 | 写入 `data/factor_pipeline/output/{symbol}_factor.parquet` |
| `cleaner/cleaner.py` | 数据质量层 | `MarketDataCleaner`：日期标准化、排序、去重、OHLCV 业务规则校验 |
| `factors/technical.py` | 技术因子 | `TechnicalFactorGenerator`：TA-Lib 计算 MACD（12/26/9）与 RSI（14）；追加 `macd`、`macd_signal`、`macd_hist`、`rsi` |
| `factors/price.py` | 价格因子 | `PriceFactorGenerator`：基于 `close` 计算日收益率与动量；追加 `return_1d`、`return_5d`、`return_10d`、`momentum_5d`、`momentum_10d` |
| `factors/volume.py` | 成交量因子 | `VolumeFactorGenerator`：基于 `volume`/`turnover` 计算成交量变化、均线、比率与换手率；追加 7 列（见下文） |
| `factors/volatility.py` | 波动率因子 | `VolatilityFactorGenerator`：基于 `high`/`low`/`close` 计算滚动收益标准差、年化历史波动率与 ATR；追加 4 列（见下文） |
| `labels/label_generator.py` | 监督学习标签 | `LabelGenerator`：基于 `close` 计算远期收益与二分类 `label`；删除末尾 `horizon` 行（默认 5） |
| `dataset/*.py` | 数据集准备 | 透传占位；`splitter.py` 未接入 `engine.py` |
| `engine.py` | 流水线编排 | 加载快照、校验输出目录、按序执行各阶段 |
| `pipeline.py` | 程序入口 | 解析 `--snapshot-dir` / `--output-dir`，运行 `FactorEngine.run_all()` |

### 校验分层

| 层级 | 模块 | 校验内容 |
|------|------|----------|
| 快照输入 | `io/loader.py` | 快照目录、manifest、daily_bars、metadata、symbols、各 symbol parquet |
| 行 schema | `io/loader.py` | parquet 必需列 |
| 数据质量 | `cleaner/cleaner.py` | 日期标准化、排序、去重、OHLCV 业务规则 |
| 输出路径 | `engine.py`（`validate_output_dir`） | 输出目录可创建且可写 |

### 输入约定

```
data/market_data/snapshots/latest/
├── manifest.json
├── stock_basic.parquet
└── daily_bars/
    ├── 000001.parquet
    └── 600000.parquet
```

必需列：

```
date, code, open, high, low, close, volume, amount, amplitude, pct_change, change, turnover
```

加载器返回**原样存储**的 DataFrame，不做排序或字段增强。

### 数据质量规则（`cleaner/cleaner.py`）

`loader.py` 读取原始 parquet 后，由 `MarketDataCleaner` 对每只股票进行标准化与校验。

#### 标准化（始终执行）

| 步骤 | 规则 |
|------|------|
| 日期 | 将 `date` 转为 `datetime64`（无法解析则报错） |
| 排序 | 按 `date` 升序排列 |
| 去重 | 删除重复 `(code, date)` 行，保留第一条 |

#### 字段检查

必须包含 loader 约定的全部列，缺失则抛出 `ValueError`。

#### OHLCV 业务规则

**仅校验非空值**（NaN 保留，不填充）。

| 规则 | 条件 | 生效条件 |
|------|------|----------|
| 最高价 | `high >= max(open, close)` | `open/high/close` 均非空 |
| 最低价 | `low <= min(open, close)` | `open/low/close` 均非空 |
| 区间 | `high >= low` | `high/low` 均非空 |
| 收盘价 | `close > 0` | `close` 非空 |
| 成交量 | `volume >= 0` | `volume` 非空 |
| 换手率 | `turnover >= 0` | `turnover` 非空 |

违反任一条规则 → `MarketDataValidationError`（含规则名、失败行数、最多 3 条样本）。

#### 明确不做的事

- 不填充 NaN
- 不生成因子或标签列
- 不做缩放或导出

### 技术因子（`factors/technical.py`）

清洗完成后，`TechnicalFactorGenerator` 基于 `close` 列追加 TA-Lib 指标。输入 DataFrame 不会被原地修改，所有新列均写入副本。

#### 输出列

| 列名 | 指标 | TA-Lib 调用 | 参数 |
|------|------|-------------|------|
| `macd` | MACD 线 | `talib.MACD` | fastperiod=12, slowperiod=26, signalperiod=9 |
| `macd_signal` | MACD 信号线 | `talib.MACD` | 同上 |
| `macd_hist` | MACD 柱 | `talib.MACD` | 同上 |
| `rsi` | 相对强弱指数 | `talib.RSI` | timeperiod=14 |

滚动窗口产生的首部 `NaN` 原样保留（不填充）。

#### 校验与错误

| 检查项 | 行为 |
|--------|------|
| 必需输入 | 必须存在 `close` 列，否则抛出 `ValueError` |
| 禁止覆盖 | 若输出列已存在，抛出 `ValueError` |

#### 明确不做的事

- 不填充或插补指标 NaN
- 不修改原始行情列

### 价格因子（`factors/price.py`）

技术因子完成后，`PriceFactorGenerator` 基于 `close` 列使用 pandas 向量化运算追加价格类因子。输入 DataFrame 不会被原地修改，所有新列均写入副本。

#### 输出列

| 列名 | 因子 | 公式 |
|------|------|------|
| `return_1d` | 1 日收益率 | `close / close.shift(1) - 1` |
| `return_5d` | 5 日收益率 | `close / close.shift(5) - 1` |
| `return_10d` | 10 日收益率 | `close / close.shift(10) - 1` |
| `momentum_5d` | 5 日动量 | `close - close.shift(5)` |
| `momentum_10d` | 10 日动量 | `close - close.shift(10)` |

`shift()` 产生的首部 `NaN` 原样保留（不填充）。

#### 校验与错误

| 检查项 | 行为 |
|--------|------|
| 必需输入 | 必须存在 `close` 列，否则抛出 `ValueError` |
| 禁止覆盖 | 若输出列已存在，抛出 `ValueError` |

#### 明确不做的事

- 不填充或插补因子 NaN
- 不修改原始行情列或上游因子列

### 成交量因子（`factors/volume.py`）

价格因子完成后，`VolumeFactorGenerator` 基于 `volume` 与 `turnover` 列使用 pandas 向量化运算追加成交量与流动性类因子。输入 DataFrame 不会被原地修改，所有新列均写入副本。

#### 输出列

| 列名 | 因子 | 公式 |
|------|------|------|
| `volume_change_1d` | 1 日成交量变化 | `volume / volume.shift(1) - 1` |
| `volume_change_5d` | 5 日成交量变化 | `volume / volume.shift(5) - 1` |
| `volume_ma_5` | 5 日成交量均线 | `volume.rolling(5).mean()` |
| `volume_ma_10` | 10 日成交量均线 | `volume.rolling(10).mean()` |
| `volume_ratio_5` | 成交量相对 5 日均线 | `volume / volume_ma_5` |
| `turnover_ma_5` | 5 日换手率均线 | `turnover.rolling(5).mean()` |
| `turnover_change_1d` | 1 日换手率变化 | `turnover / turnover.shift(1) - 1` |

`shift()` 与 `rolling()` 产生的首部 `NaN` 原样保留（不填充）。`volume_ratio_5` 依赖同阶段计算的 `volume_ma_5`。

#### 校验与错误

| 检查项 | 行为 |
|--------|------|
| 必需输入 | 必须存在 `volume` 与 `turnover` 列，否则抛出 `ValueError` |
| 禁止覆盖 | 若输出列已存在，抛出 `ValueError` |

#### 明确不做的事

- 不填充或插补因子 NaN
- 不修改原始行情列或上游因子列

### 波动率因子（`factors/volatility.py`）

成交量因子完成后，`VolatilityFactorGenerator` 基于 `high`、`low`、`close` 列追加波动率类因子。滚动指标使用 pandas，ATR 使用 TA-Lib。输入 DataFrame 不会被原地修改，所有新列均写入副本。

#### 输出列

| 列名 | 因子 | 公式 / 来源 |
|------|------|-------------|
| `rolling_std_5` | 5 日收益波动率 | `close.pct_change().rolling(5).std()` |
| `rolling_std_10` | 10 日收益波动率 | `close.pct_change().rolling(10).std()` |
| `historical_volatility_20` | 20 日年化波动率 | `close.pct_change().rolling(20).std() * sqrt(252)` |
| `atr_14` | 平均真实波幅 | `talib.ATR(high, low, close, timeperiod=14)` |

`rolling()` 与 TA-Lib 预热产生的首部 `NaN` 原样保留（不填充）。

#### 校验与错误

| 检查项 | 行为 |
|--------|------|
| 必需输入 | 必须存在 `high`、`low`、`close` 列，否则抛出 `ValueError` |
| 禁止覆盖 | 若输出列已存在，抛出 `ValueError` |

#### 明确不做的事

- 不填充或插补因子 NaN
- 不修改原始行情列或上游因子列

### 标签（`labels/label_generator.py`）

全部因子阶段完成后，`LabelGenerator` 基于 `close` 列追加监督学习目标。保留行上的因子列不会被修改；新列写入副本后，删除无未来价格的末尾行。

#### 默认参数

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `horizon` | `5` | 远期收益窗口（交易日） |
| `threshold` | `0.02` | `label = 1` 所需的最低远期收益率 |

#### 输出列

| 列名 | 定义 |
|------|------|
| `future_return` | `close.shift(-horizon) / close - 1` |
| `label` | `future_return >= threshold` 时为 `1`，否则为 `0` |

#### 末尾行删除

最后 `horizon` 行没有可观测的未来收盘价，返回前予以删除，确保导出的每行因子列不含前瞻偏差。输出行数 = 输入行数 − `horizon`（默认减 5）。

#### 校验与错误

| 检查项 | 行为 |
|--------|------|
| 必需输入 | 必须存在 `close` 列，否则抛出 `ValueError` |
| 禁止覆盖 | 若 `future_return` 或 `label` 已存在，抛出 `ValueError` |

#### 明确不做的事

- 不修改因子列
- 不做特征缩放或训练/验证/测试切分

### 输出约定

```
data/factor_pipeline/output/{symbol}_factor.parquet
```

示例：`data/factor_pipeline/output/600000_factor.parquet`

当前输出列 = 输入行情列 + 全部因子列（共 20 列，见上文各因子章节）+ `future_return` + `label`。

输出行数 = 清洗后行情行数 − `horizon`（默认 5）。示例：1,211 个交易日 → 每只股票导出 1,206 行。

### 完整工作流

**`engine.py` 中的阶段顺序：**

1. 加载数据 — `load_snapshot()` + `load_market_data()`
2. 清洗数据 — `MarketDataCleaner.clean()`：日期、排序、去重、OHLCV 规则
3. 技术因子 — `compute_technical_factors()`
4. 价格因子 — `compute_price_factors()`
5. 成交量因子 — `compute_volume_factors()`
6. 波动率因子 — `compute_volatility_factors()`
7. 生成标签 — `generate_labels()`
8. 构建数据集 — `build_dataset()`
9. 缩放数据集 — `scale_dataset()`
10. 导出 Parquet — `export_factor_dataset()`

### 运行方式

```bash
# 默认：从 data/market_data/snapshots/latest 读取
#       写入 data/factor_pipeline/output
python -m factor_pipeline.pipeline
```

```bash
python -m factor_pipeline.pipeline \
  --snapshot-dir data/market_data/snapshots/latest \
  --output-dir data/factor_pipeline/output
```

预期输出：

```
[OK] saved -> data/factor_pipeline/output/600000_factor.parquet
```

### 编程调用

```python
from factor_pipeline.engine import FactorEngine

engine = FactorEngine()
result = engine.run('600000')
print(result.output_path)
```

### 测试

```bash
python -m pytest tests/test_factor_pipeline_loader.py tests/test_factor_pipeline_cleaner.py tests/test_factor_pipeline_technical.py tests/test_factor_pipeline_price.py tests/test_factor_pipeline_volume.py tests/test_factor_pipeline_volatility.py tests/test_factor_pipeline_label_generator.py -v
```

- `test_factor_pipeline_loader.py` — 快照加载、路径校验、导出、端到端引擎
- `test_factor_pipeline_cleaner.py` — 排序、去重、OHLCV 规则、NaN 跳过策略
- `test_factor_pipeline_technical.py` — MACD/RSI 与 TA-Lib 对照、缺失列与覆盖保护
- `test_factor_pipeline_price.py` — 收益率/动量公式、NaN 行为、缺失列与覆盖保护
- `test_factor_pipeline_volume.py` — 成交量/换手率公式、NaN 行为、缺失列与覆盖保护
- `test_factor_pipeline_volatility.py` — 滚动标准差/历史波动率公式、ATR 与 TA-Lib 对照、NaN 行为、缺失列与覆盖保护
- `test_factor_pipeline_label_generator.py` — 远期收益、二分类标签、horizon/threshold 配置、末尾行删除

### 设计说明

- 沿用原 `feature_pipeline` 的快照输入约定（基于 manifest 加载）。
- **不**直接 import `market_data_pipeline`。
- **不**实现缩放（RobustScaler）或机器学习逻辑。
- 四个因子模块与 `LabelGenerator` 均已实现。
- `dataset/builder.py`、`dataset/scaler.py` 与 `dataset/splitter.py` 仍为占位；`splitter.py` 尚未接入 `engine.py`。
