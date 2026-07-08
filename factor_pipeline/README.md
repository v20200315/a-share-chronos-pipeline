# factor_pipeline

Transform raw A-share daily market data into research-ready machine learning datasets.

---

## Table of Contents

**English**
- [Overview](#overview)
- [Architecture](#architecture)
- [Directory Structure](#directory-structure)
- [Data Flow](#data-flow)
- [Supported Factors](#supported-factors)
- [Labels](#labels)
- [Dataset Builder](#dataset-builder)
- [Feature Scaling](#feature-scaling)
- [Dataset Exporter](#dataset-exporter)
- [Input Schema](#input-schema)
- [Output Schema](#output-schema)
- [Example Usage](#example-usage)
- [Running the Pipeline](#running-the-pipeline)
- [Testing](#testing)
- [Dependencies](#dependencies)
- [Design Principles](#design-principles)
- [Future Roadmap](#future-roadmap)
- [For Quant Developer Interviews](#for-quant-developer-interviews)

**中文**
- [概述](#概述)
- [架构](#架构)
- [目录结构](#目录结构)
- [数据流](#数据流)
- [支持的因子](#支持的因子)
- [标签](#标签)
- [数据集构建](#数据集构建)
- [特征缩放](#特征缩放)
- [数据集导出](#数据集导出)
- [输入 Schema](#输入-schema)
- [输出 Schema](#输出-schema)
- [使用示例](#使用示例)
- [运行流水线](#运行流水线)
- [测试](#测试)
- [依赖](#依赖)
- [设计原则](#设计原则)
- [未来路线图](#未来路线图)
- [量化开发面试](#量化开发面试)

---

## Overview

`factor_pipeline` is the second layer of **a-share-chronos-pipeline** — an industrial-grade A-share AI data production system. It consumes daily OHLCV parquet snapshots published by `market_data_pipeline` and produces per-symbol, supervised-learning-ready factor datasets for `model_pipeline` and `backtest_pipeline`.

Factor engineering sits between raw market data and model training. Models learn from **features** (derived signals), not raw prices. This module standardizes that transformation: load → validate → compute factors → generate labels → assemble a fixed schema → scale features → export parquet.

```
market_data_pipeline
        │
        ▼
factor_pipeline          ← you are here
        │
        ▼
model_pipeline
        │
        ▼
backtest_pipeline
```

**Current status:** All production stages are implemented end-to-end. Only `dataset/splitter.py` remains a pass-through placeholder and is **not** wired into `engine.py`.

---

## Architecture

### Pipeline stages

```
Raw OHLCV Parquet (snapshot)
        │
        ▼
┌───────────────────┐
│  Load Data        │  io/loader.py — manifest + per-symbol parquet
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Clean Data       │  cleaner/cleaner.py — dates, sort, dedupe, OHLCV rules
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Generate Factors │  factors/ — technical → price → volume → volatility
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Generate Labels  │  labels/label_generator.py — future_return + binary label
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Build Dataset    │  dataset/builder.py — metadata + features + targets (24 cols)
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Scale Features   │  dataset/scaler.py — RobustScaler on 20 features
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  Export Parquet   │  io/exporter.py — PyArrow write per symbol
└─────────┬─────────┘
          ▼
  {symbol}_factor.parquet
```

### Orchestration

`FactorEngine` (`engine.py`) runs all stages in order for one symbol or every symbol in the snapshot manifest. `pipeline.py` is the CLI entry point.

Each stage is a **single-responsibility module** with a class + thin wrapper function (e.g. `TechnicalFactorGenerator` / `compute_technical_factors`).

---

## Directory Structure

```
factor_pipeline/
├── __init__.py          # Exports FactorEngine, FactorEngineResult, FactorEngineBatchResult
├── paths.py             # Default paths; validate_output_dir()
├── engine.py            # Stage orchestration
├── pipeline.py          # CLI: --snapshot-dir, --output-dir
│
├── io/
│   ├── loader.py        # Snapshot manifest + per-symbol parquet load (PyArrow)
│   └── exporter.py      # Per-symbol parquet export (PyArrow DatasetExporter)
│
├── cleaner/
│   └── cleaner.py       # OHLCV standardization and business-rule validation
│
├── factors/
│   ├── technical.py     # MACD, RSI (TA-Lib)
│   ├── price.py         # Returns, momentum
│   ├── volume.py        # Volume change, MA, ratio, turnover
│   └── volatility.py    # Rolling std, historical vol, ATR
│
├── labels/
│   └── label_generator.py   # future_return + binary label
│
└── dataset/
    ├── builder.py       # Fixed 24-column research layout
    ├── scaler.py        # RobustScaler on feature columns
    └── splitter.py      # Placeholder (not wired into engine)
```

| Module | Boundary | Does NOT |
|--------|----------|----------|
| `io/loader.py` | Read snapshot parquet | Clean, factorize, export |
| `cleaner/` | Standardize + validate OHLCV | Generate factors or labels |
| `factors/` | Append factor columns | Scale, label, export |
| `labels/` | Append targets, drop tail rows | Scale or export |
| `dataset/builder.py` | Select/reorder columns | Scale or split |
| `dataset/scaler.py` | Scale features, drop feature NaNs | Export or split |
| `io/exporter.py` | Write parquet | Load, factorize, scale |
| `engine.py` | Orchestrate stages | Implement business logic |

---

## Data Flow

### Input

Published market-data snapshot from `market_data_pipeline`:

```
data/market_data/snapshots/latest/
├── manifest.json
├── stock_basic.parquet
└── daily_bars/
    ├── 000001.parquet
    └── 600000.parquet
```

`loader.py` reads `manifest.json`, resolves `daily_bars_path`, validates schema, and returns a raw `pd.DataFrame` per symbol.

### Intermediate stages

| Stage | Input rows | Output change |
|-------|------------|---------------|
| Clean | Raw parquet rows | Sorted, deduplicated; invalid OHLCV rejected |
| Factors | Cleaned rows | +20 factor columns appended to OHLCV frame |
| Labels | Factor-enriched rows | +`future_return`, +`label`; last `horizon` rows dropped |
| Build dataset | Labeled rows | Raw OHLCV stripped; 24-column layout |
| Scale | Built dataset | Feature columns scaled; rows with feature NaN dropped |
| Export | Scaled dataset | Written to `{symbol}_factor.parquet` |

### Output

```
data/factor_pipeline/output/
├── 000001_factor.parquet
└── 600000_factor.parquet
```

**Row count:** `cleaned_rows − horizon (default 5) − feature_warmup_nan_rows`

---

## Supported Factors

20 feature columns across four families.

### Technical Factors (`factors/technical.py`)

| Column | Definition | Parameters |
|--------|------------|------------|
| `macd` | TA-Lib MACD line | fast=12, slow=26, signal=9 |
| `macd_signal` | MACD signal line | same |
| `macd_hist` | MACD histogram | same |
| `rsi` | Relative Strength Index | period=14 |

### Price Factors (`factors/price.py`)

| Column | Definition |
|--------|------------|
| `return_1d` | `close / close.shift(1) - 1` |
| `return_5d` | `close / close.shift(5) - 1` |
| `return_10d` | `close / close.shift(10) - 1` |
| `momentum_5d` | `close - close.shift(5)` |
| `momentum_10d` | `close - close.shift(10)` |

### Volume Factors (`factors/volume.py`)

| Column | Definition |
|--------|------------|
| `volume_change_1d` | `volume / volume.shift(1) - 1` |
| `volume_change_5d` | `volume / volume.shift(5) - 1` |
| `volume_ma_5` | `volume.rolling(5).mean()` |
| `volume_ma_10` | `volume.rolling(10).mean()` |
| `volume_ratio_5` | `volume / volume_ma_5` |
| `turnover_ma_5` | `turnover.rolling(5).mean()` |
| `turnover_change_1d` | `turnover / turnover.shift(1) - 1` |

### Volatility Factors (`factors/volatility.py`)

| Column | Definition |
|--------|------------|
| `rolling_std_5` | `close.pct_change().rolling(5).std()` |
| `rolling_std_10` | `close.pct_change().rolling(10).std()` |
| `historical_volatility_20` | `pct_change().rolling(20).std() × √252` |
| `atr_14` | TA-Lib ATR | period=14 |

Leading `NaN` values from rolling windows and TA-Lib warm-up are **preserved**, not imputed.

---

## Labels

Module: `labels/label_generator.py`

### Columns

| Column | Definition |
|--------|------------|
| `future_return` | `close.shift(-horizon) / close - 1` |
| `label` | `1` if `future_return >= threshold`, else `0` |

### Default parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `horizon` | `5` | Forward return window (trading days) |
| `threshold` | `0.02` | Minimum return for positive class |

### Why configurable

Different research tasks need different prediction horizons (1-day vs 5-day vs 20-day) and different classification thresholds. `LabelGenerator(horizon=..., threshold=...)` exposes these without changing factor code.

### Look-ahead control

The last `horizon` rows have no observable future close and are **dropped** before return. This prevents label leakage into exported features.

---

## Dataset Builder

Module: `dataset/builder.py`

Assembles the fixed export layout from the labeled factor frame.

### Column groups

| Group | Columns | Count |
|-------|---------|-------|
| Metadata | `date`, `code` | 2 |
| Features | all 20 factor columns (technical → price → volume → volatility) | 20 |
| Targets | `future_return`, `label` | 2 |

**Total: 24 columns.** Raw OHLCV (`open`, `high`, `low`, `close`, `volume`, etc.) is excluded.

Column order: metadata → features → targets. Row count and values are preserved (no scaling, no row removal at this stage).

---

## Feature Scaling

Module: `dataset/scaler.py`

### Why RobustScaler

Financial return and volume features are heavy-tailed. A few extreme observations can dominate `StandardScaler`. `RobustScaler` uses median and IQR, making scaled features more stable under outliers — a common choice in quant ML pipelines.

### What is scaled

| Scaled | Not scaled |
|--------|------------|
| All 20 feature columns | `date`, `code`, `future_return`, `label` |

### NaN handling

Rows with `NaN` in **any** feature column are dropped before fitting. Rows are **not** dropped because of NaN in metadata or targets.

### API

```python
scaler = FeatureScaler()
scaled_df, fitted = scaler.fit_transform(df, list(FEATURE_COLUMNS))
inference_df = scaler.transform(new_df, list(FEATURE_COLUMNS))
```

Engine wrapper: `scale_dataset(df)` scales all `FEATURE_COLUMNS` from `builder.py`.

---

## Dataset Exporter

Module: `io/exporter.py`

Writes the final dataset to parquet using **PyArrow** (not `pandas.to_parquet`).

| Rule | Behavior |
|------|----------|
| Writer | `pyarrow.parquet.write_table` |
| Conversion | `pa.Table.from_pandas(df, preserve_index=False)` |
| Filename | `{symbol}_factor.parquet` (6-digit zero-padded) |
| Overwrite | Existing files replaced |

```python
path = DatasetExporter().export(df, '600000', 'data/factor_pipeline/output')
# or
path = export_factor_dataset(df, '600000', output_dir='data/factor_pipeline/output')
```

---

## Input Schema

Required columns in each `daily_bars/{symbol}.parquet` file (`io/loader.py`):

| Column | Type | Description |
|--------|------|-------------|
| `date` | date/datetime | Trading date |
| `code` | string | Stock code |
| `open` | float | Open price |
| `high` | float | High price |
| `low` | float | Low price |
| `close` | float | Close price |
| `volume` | float | Volume |
| `amount` | float | Turnover amount |
| `amplitude` | float | Amplitude (%) |
| `pct_change` | float | Percent change |
| `change` | float | Absolute change |
| `turnover` | float | Turnover rate |

### OHLCV validation rules (`cleaner/cleaner.py`)

- `high >= max(open, close)`
- `low <= min(open, close)`
- `high >= low`
- `close > 0`
- `volume >= 0`, `turnover >= 0`
- Dates standardized to `datetime64`, sorted ascending, `(code, date)` deduplicated

---

## Output Schema

### Metadata (2)

| Column | Description |
|--------|-------------|
| `date` | Trading date |
| `code` | Stock code |

### Features (20)

| Family | Columns |
|--------|---------|
| Technical | `macd`, `macd_signal`, `macd_hist`, `rsi` |
| Price | `return_1d`, `return_5d`, `return_10d`, `momentum_5d`, `momentum_10d` |
| Volume | `volume_change_1d`, `volume_change_5d`, `volume_ma_5`, `volume_ma_10`, `volume_ratio_5`, `turnover_ma_5`, `turnover_change_1d` |
| Volatility | `rolling_std_5`, `rolling_std_10`, `historical_volatility_20`, `atr_14` |

### Targets (2)

| Column | Description |
|--------|-------------|
| `future_return` | Forward return over `horizon` days |
| `label` | Binary classification label |

---

## Example Usage

### Full pipeline (recommended)

```python
from factor_pipeline.engine import FactorEngine

engine = FactorEngine(
    snapshot_dir='data/market_data/snapshots/latest',
    output_dir='data/factor_pipeline/output',
    verbose=True,
)
result = engine.run('600000')
print(result.output_path)
# data/factor_pipeline/output/600000_factor.parquet
```

### Stage-by-stage (programmatic)

```python
from factor_pipeline.io.loader import load_snapshot, load_market_data
from factor_pipeline.cleaner.cleaner import clean
from factor_pipeline.factors.technical import compute_technical_factors
from factor_pipeline.factors.price import compute_price_factors
from factor_pipeline.factors.volume import compute_volume_factors
from factor_pipeline.factors.volatility import compute_volatility_factors
from factor_pipeline.labels.label_generator import generate_labels
from factor_pipeline.dataset.builder import build_dataset
from factor_pipeline.dataset.scaler import scale_dataset
from factor_pipeline.io.exporter import export_factor_dataset

snapshot = load_snapshot('data/market_data/snapshots/latest')
df = load_market_data('600000', snapshot=snapshot)
df = clean(df)
df = compute_technical_factors(df)
df = compute_price_factors(df)
df = compute_volume_factors(df)
df = compute_volatility_factors(df)
df = generate_labels(df)
df = build_dataset(df)
df = scale_dataset(df)
path = export_factor_dataset(df, '600000', output_dir='data/factor_pipeline/output')
```

### Custom labels

```python
from factor_pipeline.labels.label_generator import LabelGenerator

generator = LabelGenerator(horizon=10, threshold=0.03)
df = generator.generate(factor_df)
```

---

## Running the Pipeline

### Prerequisites

```bash
conda env create -f environment.yml
conda activate chronos_env
```

Ensure `market_data_pipeline` has published a snapshot to `data/market_data/snapshots/latest/`.

### CLI

```bash
# Defaults: snapshot from data/market_data/snapshots/latest
#           output to data/factor_pipeline/output
python -m factor_pipeline.pipeline
```

```bash
python -m factor_pipeline.pipeline \
  --snapshot-dir data/market_data/snapshots/latest \
  --output-dir data/factor_pipeline/output
```

### Example output

```
[INFO] starting factor pipeline
[INFO] snapshot -> data/market_data/snapshots/latest
[INFO] daily bars -> data/market_data/snapshots/latest/daily_bars
[INFO] symbols -> 000001, 600000
[INFO] output -> data/factor_pipeline/output
[INFO] processing symbol 000001 (1/2)
...
[OK] saved -> data/factor_pipeline/output/000001_factor.parquet
[OK] saved -> data/factor_pipeline/output/600000_factor.parquet
```

---

## Testing

```bash
python -m pytest \
  tests/test_factor_pipeline_loader.py \
  tests/test_factor_pipeline_cleaner.py \
  tests/test_factor_pipeline_technical.py \
  tests/test_factor_pipeline_price.py \
  tests/test_factor_pipeline_volume.py \
  tests/test_factor_pipeline_volatility.py \
  tests/test_factor_pipeline_label_generator.py \
  tests/test_factor_pipeline_dataset_builder.py \
  tests/test_factor_pipeline_scaler.py \
  tests/test_factor_pipeline_exporter.py \
  -v
```

Each stage has dedicated unit tests covering formulas, NaN behavior, validation guards, and integration smoke tests.

---

## Dependencies

### Used directly by `factor_pipeline`

| Package | Role |
|---------|------|
| **pandas** | DataFrame operations across all stages |
| **numpy** | Numerical arrays for TA-Lib and vectorized math |
| **pyarrow** | Parquet read (loader) and write (exporter) |
| **ta-lib** | MACD, RSI, ATR indicators |
| **scikit-learn** | `RobustScaler` in feature scaling |
| **pytest** | Unit and integration tests |

### Project environment (shared, not imported by this module)

| Package | Notes |
|---------|-------|
| **numba** | Used elsewhere in the monorepo; not referenced in `factor_pipeline/` |
| **pydantic** | Configuration validation in other pipelines |
| **lightgbm** | Planned for `model_pipeline` |
| **optuna** | Planned for hyperparameter tuning in `model_pipeline` |

---

## Design Principles

| Principle | How it applies |
|-----------|----------------|
| **Layered architecture** | Each pipeline (`market_data` → `factor` → `model` → `backtest`) has a narrow contract |
| **Single responsibility** | One module per stage; `engine.py` only orchestrates |
| **Stable data contracts** | Fixed input columns (12 OHLCV fields), fixed output layout (24 columns) |
| **Parquet-based exchange** | Snapshots in, factor datasets out — no database coupling |
| **Research vs model dataset** | Builder produces a research layout; scaler prepares features for ML without touching targets |
| **Extensibility** | New factor families = new module + register in `engine.py`; label horizon/threshold configurable |
| **Fail fast** | Validation at load, clean, factor, label, build, scale, and export stages |
| **No look-ahead** | Label tail rows dropped; features computed from past data only |

---

## Future Roadmap

| Area | Version 2 idea |
|------|----------------|
| Factors | Cross-sectional ranks, industry-neutral features, fundamental ratios |
| Splitting | Wire `TimeSeriesSplit` into `dataset/splitter.py` |
| Modeling | LightGBM training in `model_pipeline` |
| Tuning | Optuna integration for horizon/threshold/feature selection |
| Backtest | Backtrader integration in `backtest_pipeline` |
| Performance | Numba-accelerated custom indicators where TA-Lib is insufficient |

---

## For Quant Developer Interviews

This module demonstrates:

| Skill area | Evidence |
|------------|----------|
| **Data engineering** | Snapshot manifest loading, PyArrow parquet I/O, schema validation |
| **Feature engineering** | 20 factors across technical/price/volume/volatility families with correct warm-up NaN handling |
| **ML dataset construction** | Fixed metadata/feature/target layout, label generation with horizon control, look-ahead prevention |
| **Pipeline design** | 10-stage linear DAG, class + wrapper pattern, engine orchestration |
| **Software architecture** | Module boundaries, frozen dataclass results, path validation layer |
| **Testing** | Per-stage unit tests with formula verification against TA-Lib reference |
| **Production readiness** | Structured logging, input validation, writable-path checks, overwrite-safe export |

---

# 中文

---

## 概述

`factor_pipeline` 是 **a-share-chronos-pipeline** 的第二层——面向 A 股的工业级 AI 数据生产系统。它读取 `market_data_pipeline` 发布的日频 OHLCV Parquet 快照，为 `model_pipeline` 和 `backtest_pipeline` 生成按股票拆分的、可用于监督学习的研究数据集。

因子工程位于原始行情与模型训练之间。模型从**特征**（衍生信号）中学习，而非原始价格。本模块将这一转化标准化：加载 → 校验 → 计算因子 → 生成标签 → 固定 Schema 组装 → 特征缩放 → 导出 Parquet。

```
market_data_pipeline
        │
        ▼
factor_pipeline          ← 当前模块
        │
        ▼
model_pipeline
        │
        ▼
backtest_pipeline
```

**当前状态：** 全部生产阶段已端到端实现。仅 `dataset/splitter.py` 仍为透传占位，**未**接入 `engine.py`。

---

## 架构

### 流水线阶段

```
原始 OHLCV Parquet（快照）
        │
        ▼
┌───────────────────┐
│  加载数据          │  io/loader.py — manifest + 单股 parquet
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  清洗数据          │  cleaner/cleaner.py — 日期、排序、去重、OHLCV 规则
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  生成因子          │  factors/ — 技术 → 价格 → 成交量 → 波动率
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  生成标签          │  labels/label_generator.py — future_return + 二分类 label
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  构建数据集        │  dataset/builder.py — 元数据 + 特征 + 目标（24 列）
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  特征缩放          │  dataset/scaler.py — 20 个特征的 RobustScaler
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  导出 Parquet      │  io/exporter.py — PyArrow 按股票写入
└─────────┬─────────┘
          ▼
  {symbol}_factor.parquet
```

### 编排

`FactorEngine`（`engine.py`）按顺序对单只股票或 manifest 中全部股票执行各阶段。`pipeline.py` 为 CLI 入口。

每个阶段为**单一职责模块**，采用「类 + 薄封装函数」模式（如 `TechnicalFactorGenerator` / `compute_technical_factors`）。

---

## 目录结构

```
factor_pipeline/
├── __init__.py          # 导出 FactorEngine、FactorEngineResult、FactorEngineBatchResult
├── paths.py             # 默认路径；validate_output_dir()
├── engine.py            # 阶段编排
├── pipeline.py          # CLI：--snapshot-dir、--output-dir
│
├── io/
│   ├── loader.py        # 快照 manifest + 单股 parquet 加载（PyArrow）
│   └── exporter.py      # 单股 parquet 导出（PyArrow DatasetExporter）
│
├── cleaner/
│   └── cleaner.py       # OHLCV 标准化与业务规则校验
│
├── factors/
│   ├── technical.py     # MACD、RSI（TA-Lib）
│   ├── price.py         # 收益率、动量
│   ├── volume.py        # 成交量变化、均线、比率、换手率
│   └── volatility.py    # 滚动标准差、历史波动率、ATR
│
├── labels/
│   └── label_generator.py   # future_return + 二分类 label
│
└── dataset/
    ├── builder.py       # 固定 24 列研究布局
    ├── scaler.py        # 特征列 RobustScaler
    └── splitter.py      # 占位（未接入 engine）
```

| 模块 | 职责边界 | 不做 |
|------|----------|------|
| `io/loader.py` | 读取快照 parquet | 清洗、算因子、导出 |
| `cleaner/` | 标准化 + 校验 OHLCV | 生成因子或标签 |
| `factors/` | 追加因子列 | 缩放、打标签、导出 |
| `labels/` | 追加目标列、删除末尾行 | 缩放或导出 |
| `dataset/builder.py` | 选取/重排列 | 缩放或切分 |
| `dataset/scaler.py` | 缩放特征、删除特征 NaN 行 | 导出或切分 |
| `io/exporter.py` | 写入 parquet | 加载、算因子、缩放 |
| `engine.py` | 编排各阶段 | 实现业务逻辑 |

---

## 数据流

### 输入

`market_data_pipeline` 发布的行情快照：

```
data/market_data/snapshots/latest/
├── manifest.json
├── stock_basic.parquet
└── daily_bars/
    ├── 000001.parquet
    └── 600000.parquet
```

`loader.py` 读取 `manifest.json`，解析 `daily_bars_path`，校验 schema，按股票返回原始 `pd.DataFrame`。

### 中间阶段

| 阶段 | 输入行数 | 输出变化 |
|------|----------|----------|
| 清洗 | 原始 parquet 行 | 排序、去重；非法 OHLCV 拒绝 |
| 因子 | 清洗后行 | +20 列因子追加到 OHLCV 帧 |
| 标签 | 含因子行 | +`future_return`、+`label`；删除末尾 `horizon` 行 |
| 构建数据集 | 含标签行 | 去除原始 OHLCV；24 列布局 |
| 缩放 | 构建后数据集 | 特征列缩放；删除特征 NaN 行 |
| 导出 | 缩放后数据集 | 写入 `{symbol}_factor.parquet` |

### 输出

```
data/factor_pipeline/output/
├── 000001_factor.parquet
└── 600000_factor.parquet
```

**行数：** `清洗后行数 − horizon（默认 5）− 因子预热期 NaN 行数`

---

## 支持的因子

共 20 个特征列，分四个族。

### 技术因子（`factors/technical.py`）

| 列名 | 定义 | 参数 |
|------|------|------|
| `macd` | TA-Lib MACD 线 | fast=12, slow=26, signal=9 |
| `macd_signal` | MACD 信号线 | 同上 |
| `macd_hist` | MACD 柱 | 同上 |
| `rsi` | 相对强弱指数 | period=14 |

### 价格因子（`factors/price.py`）

| 列名 | 定义 |
|------|------|
| `return_1d` | `close / close.shift(1) - 1` |
| `return_5d` | `close / close.shift(5) - 1` |
| `return_10d` | `close / close.shift(10) - 1` |
| `momentum_5d` | `close - close.shift(5)` |
| `momentum_10d` | `close - close.shift(10)` |

### 成交量因子（`factors/volume.py`）

| 列名 | 定义 |
|------|------|
| `volume_change_1d` | `volume / volume.shift(1) - 1` |
| `volume_change_5d` | `volume / volume.shift(5) - 1` |
| `volume_ma_5` | `volume.rolling(5).mean()` |
| `volume_ma_10` | `volume.rolling(10).mean()` |
| `volume_ratio_5` | `volume / volume_ma_5` |
| `turnover_ma_5` | `turnover.rolling(5).mean()` |
| `turnover_change_1d` | `turnover / turnover.shift(1) - 1` |

### 波动率因子（`factors/volatility.py`）

| 列名 | 定义 |
|------|------|
| `rolling_std_5` | `close.pct_change().rolling(5).std()` |
| `rolling_std_10` | `close.pct_change().rolling(10).std()` |
| `historical_volatility_20` | `pct_change().rolling(20).std() × √252` |
| `atr_14` | TA-Lib ATR | period=14 |

滚动窗口与 TA-Lib 预热产生的首部 `NaN` **保留**，不做填充。

---

## 标签

模块：`labels/label_generator.py`

### 列

| 列名 | 定义 |
|------|------|
| `future_return` | `close.shift(-horizon) / close - 1` |
| `label` | `future_return >= threshold` 时为 `1`，否则为 `0` |

### 默认参数

| 参数 | 默认值 | 用途 |
|------|--------|------|
| `horizon` | `5` | 远期收益窗口（交易日） |
| `threshold` | `0.02` | 正类所需的最低收益率 |

### 为何可配置

不同研究任务需要不同的预测周期（1 日、5 日、20 日）和分类阈值。`LabelGenerator(horizon=..., threshold=...)` 无需修改因子代码即可调整。

### 前瞻控制

最后 `horizon` 行没有可观测的未来收盘价，返回前**删除**，防止标签泄漏到导出特征中。

---

## 数据集构建

模块：`dataset/builder.py`

从含标签的因子帧组装固定导出布局。

### 列分组

| 分组 | 列 | 数量 |
|------|-----|------|
| 元数据 | `date`、`code` | 2 |
| 特征 | 全部 20 个因子列（技术 → 价格 → 成交量 → 波动率） | 20 |
| 目标 | `future_return`、`label` | 2 |

**共 24 列。** 原始 OHLCV（`open`、`high`、`low`、`close`、`volume` 等）不包含在内。

列顺序：元数据 → 特征 → 目标。保留行数与数值（此阶段不缩放、不删行）。

---

## 特征缩放

模块：`dataset/scaler.py`

### 为何使用 RobustScaler

金融收益与成交量特征呈厚尾分布，少量极端值可主导 `StandardScaler`。`RobustScaler` 基于中位数与 IQR，在异常值下更稳健——量化 ML 流水线中的常见选择。

### 缩放范围

| 缩放 | 不缩放 |
|------|--------|
| 全部 20 个特征列 | `date`、`code`、`future_return`、`label` |

### NaN 处理

**任一**特征列为 NaN 的行在拟合前删除。不因元数据或目标列 NaN 删行。

### API

```python
scaler = FeatureScaler()
scaled_df, fitted = scaler.fit_transform(df, list(FEATURE_COLUMNS))
inference_df = scaler.transform(new_df, list(FEATURE_COLUMNS))
```

引擎封装：`scale_dataset(df)` 缩放 `builder.py` 中的全部 `FEATURE_COLUMNS`。

---

## 数据集导出

模块：`io/exporter.py`

使用 **PyArrow** 将最终数据集写入 Parquet（不用 `pandas.to_parquet`）。

| 规则 | 行为 |
|------|------|
| 写入 | `pyarrow.parquet.write_table` |
| 转换 | `pa.Table.from_pandas(df, preserve_index=False)` |
| 文件名 | `{symbol}_factor.parquet`（6 位补零） |
| 覆盖 | 已存在文件直接替换 |

```python
path = DatasetExporter().export(df, '600000', 'data/factor_pipeline/output')
# 或
path = export_factor_dataset(df, '600000', output_dir='data/factor_pipeline/output')
```

---

## 输入 Schema

每个 `daily_bars/{symbol}.parquet` 的必需列（`io/loader.py`）：

| 列名 | 类型 | 说明 |
|------|------|------|
| `date` | date/datetime | 交易日期 |
| `code` | string | 股票代码 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | float | 成交量 |
| `amount` | float | 成交额 |
| `amplitude` | float | 振幅 |
| `pct_change` | float | 涨跌幅 |
| `change` | float | 涨跌额 |
| `turnover` | float | 换手率 |

### OHLCV 校验规则（`cleaner/cleaner.py`）

- `high >= max(open, close)`
- `low <= min(open, close)`
- `high >= low`
- `close > 0`
- `volume >= 0`、`turnover >= 0`
- 日期标准化为 `datetime64`、升序排列、`(code, date)` 去重

---

## 输出 Schema

### 元数据（2 列）

| 列名 | 说明 |
|------|------|
| `date` | 交易日期 |
| `code` | 股票代码 |

### 特征（20 列）

| 族 | 列名 |
|----|------|
| 技术 | `macd`, `macd_signal`, `macd_hist`, `rsi` |
| 价格 | `return_1d`, `return_5d`, `return_10d`, `momentum_5d`, `momentum_10d` |
| 成交量 | `volume_change_1d`, `volume_change_5d`, `volume_ma_5`, `volume_ma_10`, `volume_ratio_5`, `turnover_ma_5`, `turnover_change_1d` |
| 波动率 | `rolling_std_5`, `rolling_std_10`, `historical_volatility_20`, `atr_14` |

### 目标（2 列）

| 列名 | 说明 |
|------|------|
| `future_return` | `horizon` 日远期收益 |
| `label` | 二分类标签 |

---

## 使用示例

### 完整流水线（推荐）

```python
from factor_pipeline.engine import FactorEngine

engine = FactorEngine(
    snapshot_dir='data/market_data/snapshots/latest',
    output_dir='data/factor_pipeline/output',
    verbose=True,
)
result = engine.run('600000')
print(result.output_path)
```

### 逐阶段调用

```python
from factor_pipeline.io.loader import load_snapshot, load_market_data
from factor_pipeline.cleaner.cleaner import clean
from factor_pipeline.factors.technical import compute_technical_factors
from factor_pipeline.factors.price import compute_price_factors
from factor_pipeline.factors.volume import compute_volume_factors
from factor_pipeline.factors.volatility import compute_volatility_factors
from factor_pipeline.labels.label_generator import generate_labels
from factor_pipeline.dataset.builder import build_dataset
from factor_pipeline.dataset.scaler import scale_dataset
from factor_pipeline.io.exporter import export_factor_dataset

snapshot = load_snapshot('data/market_data/snapshots/latest')
df = load_market_data('600000', snapshot=snapshot)
df = clean(df)
df = compute_technical_factors(df)
df = compute_price_factors(df)
df = compute_volume_factors(df)
df = compute_volatility_factors(df)
df = generate_labels(df)
df = build_dataset(df)
df = scale_dataset(df)
path = export_factor_dataset(df, '600000', output_dir='data/factor_pipeline/output')
```

### 自定义标签

```python
from factor_pipeline.labels.label_generator import LabelGenerator

generator = LabelGenerator(horizon=10, threshold=0.03)
df = generator.generate(factor_df)
```

---

## 运行流水线

### 环境准备

```bash
conda env create -f environment.yml
conda activate chronos_env
```

确保 `market_data_pipeline` 已将快照发布到 `data/market_data/snapshots/latest/`。

### 命令行

```bash
python -m factor_pipeline.pipeline
```

```bash
python -m factor_pipeline.pipeline \
  --snapshot-dir data/market_data/snapshots/latest \
  --output-dir data/factor_pipeline/output
```

### 示例输出

```
[INFO] starting factor pipeline
[INFO] snapshot -> data/market_data/snapshots/latest
...
[OK] saved -> data/factor_pipeline/output/000001_factor.parquet
[OK] saved -> data/factor_pipeline/output/600000_factor.parquet
```

---

## 测试

```bash
python -m pytest \
  tests/test_factor_pipeline_loader.py \
  tests/test_factor_pipeline_cleaner.py \
  tests/test_factor_pipeline_technical.py \
  tests/test_factor_pipeline_price.py \
  tests/test_factor_pipeline_volume.py \
  tests/test_factor_pipeline_volatility.py \
  tests/test_factor_pipeline_label_generator.py \
  tests/test_factor_pipeline_dataset_builder.py \
  tests/test_factor_pipeline_scaler.py \
  tests/test_factor_pipeline_exporter.py \
  -v
```

每个阶段有独立单元测试，覆盖公式、NaN 行为、校验保护与集成冒烟测试。

---

## 依赖

### `factor_pipeline` 直接使用

| 包 | 用途 |
|----|------|
| **pandas** | 各阶段 DataFrame 操作 |
| **numpy** | TA-Lib 与向量化计算的数组 |
| **pyarrow** | Parquet 读取（loader）与写入（exporter） |
| **ta-lib** | MACD、RSI、ATR 指标 |
| **scikit-learn** | 特征缩放中的 `RobustScaler` |
| **pytest** | 单元与集成测试 |

### 项目环境（共享，本模块未直接 import）

| 包 | 说明 |
|----|------|
| **numba** | 用于 monorepo 其他模块；`factor_pipeline/` 未引用 |
| **pydantic** | 其他流水线的配置校验 |
| **lightgbm** | 计划用于 `model_pipeline` |
| **optuna** | 计划用于 `model_pipeline` 超参调优 |

---

## 设计原则

| 原则 | 实践 |
|------|------|
| **分层架构** | 各流水线（`market_data` → `factor` → `model` → `backtest`）职责清晰、接口稳定 |
| **单一职责** | 每阶段一个模块；`engine.py` 仅编排 |
| **稳定数据契约** | 固定输入列（12 个 OHLCV 字段）、固定输出布局（24 列） |
| **Parquet 交换** | 快照进、因子数据集出——无数据库耦合 |
| **研究集 vs 模型集** | Builder 产出研究布局；Scaler 仅处理特征，不触碰目标 |
| **可扩展** | 新因子族 = 新模块 + 注册到 `engine.py`；标签 horizon/threshold 可配置 |
| **快速失败** | 加载、清洗、因子、标签、构建、缩放、导出各阶段均有校验 |
| **无前瞻** | 标签末尾行删除；特征仅基于历史数据计算 |

---

## 未来路线图

| 方向 | V2 设想 |
|------|---------|
| 因子 | 截面排名、行业中性特征、基本面比率 |
| 切分 | 将 `TimeSeriesSplit` 接入 `dataset/splitter.py` |
| 建模 | `model_pipeline` 中 LightGBM 训练 |
| 调参 | Optuna 集成 horizon/threshold/特征选择 |
| 回测 | `backtest_pipeline` 中 Backtrader 集成 |
| 性能 | TA-Lib 不足时用 Numba 加速自定义指标 |

---

## 量化开发面试

本模块可展示：

| 能力 | 体现 |
|------|------|
| **数据工程** | 快照 manifest 加载、PyArrow Parquet 读写、Schema 校验 |
| **特征工程** | 4 族 20 个因子，正确处理预热期 NaN |
| **ML 数据集构建** | 固定元数据/特征/目标布局，可配置标签，防止前瞻 |
| **流水线设计** | 10 阶段线性 DAG，类 + 封装函数，引擎编排 |
| **软件架构** | 模块边界、frozen dataclass 结果、路径校验层 |
| **测试** | 分阶段单元测试，公式与 TA-Lib 参照验证 |
| **生产就绪** | 结构化日志、输入校验、可写路径检查、安全覆盖导出 |
