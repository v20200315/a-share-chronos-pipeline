# Factor Pipeline / 因子流水线

---

## English

### Overview

`factor_pipeline` is the second layer in the A-share quantitative research stack. It consumes daily market data published by `market_data_pipeline` and produces per-symbol factor datasets for downstream `alpha_model_pipeline` and `backtest_pipeline`.

The pipeline is **wired end-to-end**. Input loading, snapshot validation, output-directory checks, and the **data quality layer** (`cleaner/`) are implemented. Factor, dataset, and label stages remain placeholders until real logic is added.

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
│   ├── technical.py         # Technical factor stage (placeholder)
│   ├── price.py             # Price factor stage (placeholder)
│   ├── volume.py            # Volume factor stage (placeholder)
│   └── volatility.py        # Volatility factor stage (placeholder)
│
├── labels/
│   ├── __init__.py
│   └── label_generator.py   # Label generation stage (placeholder)
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
| `factors/*.py` | Factor engineering | Pass-through placeholders |
| `labels/label_generator.py` | Supervised labels | Adds temporary column `label = 0` |
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

### Output Contract

```
data/factor_pipeline/output/{symbol}_factor.parquet
```

Example: `data/factor_pipeline/output/600000_factor.parquet`

Current output columns = input market-data columns + `label`.

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
    │                        │            labels/label_generator.py (label=0)
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
pytest tests/test_factor_pipeline_loader.py tests/test_factor_pipeline_cleaner.py -v
```

- `test_factor_pipeline_loader.py` — snapshot loading, path validation, exporter, end-to-end engine
- `test_factor_pipeline_cleaner.py` — date sort, dedupe, OHLCV rules, NaN skip policy

### Design Notes

- Replaces the older `feature_pipeline` input contract (snapshot-based loading).
- Does **not** import `market_data_pipeline` directly.
- Does **not** implement real factors (MACD, RSI, momentum, etc.), scaling (RobustScaler), or ML.
- `dataset/splitter.py` is reserved for future train/validation/test splitting and is not yet wired into `engine.py`.

---

## 中文

### 概述

`factor_pipeline` 是 A 股量化研究体系中的第二层。它读取 `market_data_pipeline` 发布的日频行情快照，为下游的 `alpha_model_pipeline` 和 `backtest_pipeline` 生成按股票代码拆分的因子数据集。

流水线已**端到端打通**。输入加载、快照校验、输出目录校验以及**数据质量层**（`cleaner/`）已实现。因子、数据集与标签阶段仍为占位，待后续接入真实逻辑。

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
├── factors/                 # 因子阶段（占位）
├── labels/                  # 标签阶段（占位，临时 label=0）
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
| `factors/*.py` | 因子工程 | 透传占位 |
| `labels/label_generator.py` | 标签 | 添加临时列 `label = 0` |
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

### 输出约定

```
data/factor_pipeline/output/{symbol}_factor.parquet
```

示例：`data/factor_pipeline/output/600000_factor.parquet`

当前输出列 = 输入行情列 + `label`。

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
pytest tests/test_factor_pipeline_loader.py tests/test_factor_pipeline_cleaner.py -v
```

- `test_factor_pipeline_loader.py` — 快照加载、路径校验、导出、端到端引擎
- `test_factor_pipeline_cleaner.py` — 排序、去重、OHLCV 规则、NaN 跳过策略

### 设计说明

- 沿用原 `feature_pipeline` 的快照输入约定（基于 manifest 加载）。
- **不**直接 import `market_data_pipeline`。
- **不**实现真实因子（MACD、RSI、动量等）、缩放（RobustScaler）或机器学习逻辑。
- `dataset/splitter.py` 预留给后续训练/验证/测试切分，尚未接入 `engine.py`。
