# Factor Pipeline / 因子流水线

---

## English

### Overview

`factor_pipeline` is the second layer in the A-share quantitative research stack. It consumes daily market data published by `market_data_pipeline` and produces per-symbol factor datasets for downstream `alpha_model_pipeline` and `backtest_pipeline`.

This package is currently a **skeleton implementation**. Every stage is wired end-to-end, but most modules are placeholders that pass the DataFrame through unchanged. The goal is to make the full pipeline executable before real factor logic is added.

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
├── paths.py                 # Default input/output path constants
├── engine.py                # Orchestrates all stages in order
├── pipeline.py              # CLI entry point for one symbol
├── README.md
│
├── io/
│   ├── __init__.py          # Re-exports loader and exporter public APIs
│   ├── loader.py            # Load snapshot manifest and one symbol parquet
│   └── exporter.py          # Write factor parquet to output directory
│
├── cleaner/
│   ├── __init__.py
│   └── cleaner.py           # Data cleaning stage (placeholder)
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
└── output/                  # Generated factor parquet files (git-ignored)
    └── {symbol}_factor.parquet
```

### File Responsibilities

| File | Responsibility | Current Behavior |
|------|----------------|------------------|
| `paths.py` | Defines default paths | `MARKET_DATA_SNAPSHOT_LATEST`, `FACTOR_OUTPUT_DIR` |
| `io/loader.py` | Read market data | Loads `manifest.json`, resolves `daily_bars_path`, reads `{symbol}.parquet` via PyArrow, validates required columns, returns raw DataFrame |
| `io/exporter.py` | Persist factor output | Writes `factor_pipeline/output/{symbol}_factor.parquet` |
| `cleaner/cleaner.py` | Clean raw bars | Pass-through placeholder |
| `factors/base.py` | Shared factor utility | `pass_through()` helper |
| `factors/technical.py` | Technical factors | Pass-through placeholder |
| `factors/price.py` | Price factors | Pass-through placeholder |
| `factors/volume.py` | Volume factors | Pass-through placeholder |
| `factors/volatility.py` | Volatility factors | Pass-through placeholder |
| `labels/label_generator.py` | Supervised labels | Adds temporary column `label = 0` |
| `dataset/builder.py` | Assemble model dataset | Pass-through placeholder |
| `dataset/scaler.py` | Scale features | Pass-through placeholder |
| `dataset/splitter.py` | Split dataset | Pass-through placeholder; **not called by `engine.py` yet** |
| `engine.py` | Pipeline orchestration | Calls every active stage sequentially for one symbol |
| `pipeline.py` | Program entry point | Parses CLI args and runs `FactorEngine` |

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

### Output Contract

```
factor_pipeline/output/{symbol}_factor.parquet
```

Example: `factor_pipeline/output/600000_factor.parquet`

Current output columns = input market-data columns + `label`.

### Full Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  pipeline.py  (CLI)                                             │
│  python -m factor_pipeline.pipeline 600000                      │
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
 load_snapshot()        clean(df)               compute_technical_factors(df)
 load_market_data()                              │
    │                        │                        ▼
    │                        │               factors/price.py
    │                        │               compute_price_factors(df)
    │                        │                        │
    │                        │                        ▼
    │                        │               factors/volume.py
    │                        │               compute_volume_factors(df)
    │                        │                        │
    │                        │                        ▼
    │                        │               factors/volatility.py
    │                        │               compute_volatility_factors(df)
    │                        │                        │
    │                        │                        ▼
    │                        │            labels/label_generator.py
    │                        │            generate_labels(df)  → adds label=0
    │                        │                        │
    │                        │                        ▼
    │                        │               dataset/builder.py
    │                        │               build_dataset(df)
    │                        │                        │
    │                        │                        ▼
    │                        │               dataset/scaler.py
    │                        │               scale_dataset(df)
    │                        │                        │
    └────────────────────────┴────────────────────────┘
                             │
                             ▼
                    io/exporter.py
                    export_factor_dataset(df, symbol)
                             │
                             ▼
              factor_pipeline/output/600000_factor.parquet
```

**Stage order in `engine.py`:**

1. Load Data — `load_snapshot()` + `load_market_data()`
2. Clean Data — `clean()`
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
# Default: read from data/market_data/snapshots/latest
python -m factor_pipeline.pipeline 600000
```

```bash
# Override snapshot and output directories
python -m factor_pipeline.pipeline 600000 \
  --snapshot-dir data/market_data/snapshots/latest \
  --output-dir factor_pipeline/output
```

```bash
# Use a raw daily-bars directory before a snapshot is published
python -m factor_pipeline.pipeline 600000 \
  --daily-bars-dir data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d
```

Expected stdout:

```
[OK] saved -> factor_pipeline/output/600000_factor.parquet
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
pytest tests/test_factor_pipeline_loader.py -v
```

Covers snapshot loading, symbol normalization, error handling, exporter output, and end-to-end engine execution.

### Design Notes

- Replaces the older `feature_pipeline` input contract (snapshot-based loading).
- Does **not** import `market_data_pipeline` directly.
- Does **not** implement real factors (MACD, RSI, momentum, etc.), scaling (RobustScaler), or ML.
- `dataset/splitter.py` is reserved for future train/validation/test splitting and is not yet wired into `engine.py`.

---

## 中文

### 概述

`factor_pipeline` 是 A 股量化研究体系中的第二层。它读取 `market_data_pipeline` 发布的日频行情快照，为下游的 `alpha_model_pipeline` 和 `backtest_pipeline` 生成按股票代码拆分的因子数据集。

当前版本为**骨架实现**。所有阶段已串联打通，但大多数模块为占位实现，仅将 DataFrame 原样传递到下一阶段。目的是在接入真实因子逻辑之前，先保证整条流水线可执行。

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
├── paths.py                 # 默认输入/输出路径常量
├── engine.py                # 按顺序编排所有阶段
├── pipeline.py              # 单只股票 CLI 入口
├── README.md
│
├── io/
│   ├── __init__.py          # 导出 loader 与 exporter 公共 API
│   ├── loader.py            # 读取快照 manifest 与单只股票 parquet
│   └── exporter.py          # 将因子数据写入输出目录
│
├── cleaner/
│   ├── __init__.py
│   └── cleaner.py           # 数据清洗阶段（占位）
│
├── factors/
│   ├── __init__.py
│   ├── base.py              # 因子阶段共用透传工具
│   ├── technical.py         # 技术因子阶段（占位）
│   ├── price.py             # 价格因子阶段（占位）
│   ├── volume.py            # 成交量因子阶段（占位）
│   └── volatility.py        # 波动率因子阶段（占位）
│
├── labels/
│   ├── __init__.py
│   └── label_generator.py   # 标签生成阶段（占位）
│
├── dataset/
│   ├── __init__.py
│   ├── builder.py           # 数据集组装阶段（占位）
│   ├── scaler.py            # 特征缩放阶段（占位）
│   └── splitter.py          # 训练/验证/测试切分（占位，尚未接入 engine）
│
└── output/                  # 生成的因子 parquet 文件（git 忽略）
    └── {symbol}_factor.parquet
```

### 文件职责

| 文件 | 职责 | 当前行为 |
|------|------|----------|
| `paths.py` | 定义默认路径 | `MARKET_DATA_SNAPSHOT_LATEST`、`FACTOR_OUTPUT_DIR` |
| `io/loader.py` | 读取行情数据 | 读取 `manifest.json`，解析 `daily_bars_path`，通过 PyArrow 读取 `{symbol}.parquet`，校验必需列，返回原始 DataFrame |
| `io/exporter.py` | 持久化因子输出 | 写入 `factor_pipeline/output/{symbol}_factor.parquet` |
| `cleaner/cleaner.py` | 清洗原始行情 | 透传占位 |
| `factors/base.py` | 因子共用工具 | `pass_through()` 辅助函数 |
| `factors/technical.py` | 技术因子 | 透传占位 |
| `factors/price.py` | 价格因子 | 透传占位 |
| `factors/volume.py` | 成交量因子 | 透传占位 |
| `factors/volatility.py` | 波动率因子 | 透传占位 |
| `labels/label_generator.py` | 监督学习标签 | 添加临时列 `label = 0` |
| `dataset/builder.py` | 组装建模数据集 | 透传占位 |
| `dataset/scaler.py` | 特征缩放 | 透传占位 |
| `dataset/splitter.py` | 数据集切分 | 透传占位；**尚未被 `engine.py` 调用** |
| `engine.py` | 流水线编排 | 对单只股票按序调用各活跃阶段 |
| `pipeline.py` | 程序入口 | 解析 CLI 参数并运行 `FactorEngine` |

### 输入约定

从已发布的行情快照读取数据：

```
data/market_data/snapshots/latest/
├── manifest.json
├── stock_basic.parquet
└── daily_bars/
    ├── 000001.parquet
    └── 600000.parquet
```

`loader.py` 读取 `manifest.json` 并解析 `daily_bars_path`。每只股票日线 parquet 必须包含以下字段：

```
date, code, open, high, low, close, volume, amount, amplitude, pct_change, change, turnover
```

加载器返回**原样存储**的 DataFrame，不做排序、标准化或字段增强。

### 输出约定

```
factor_pipeline/output/{symbol}_factor.parquet
```

示例：`factor_pipeline/output/600000_factor.parquet`

当前输出列 = 输入行情列 + `label`。

### 完整工作流

```
┌─────────────────────────────────────────────────────────────────┐
│  pipeline.py  (CLI)                                             │
│  python -m factor_pipeline.pipeline 600000                      │
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
 load_snapshot()        clean(df)               compute_technical_factors(df)
 load_market_data()                              │
    │                        │                        ▼
    │                        │               factors/price.py
    │                        │               compute_price_factors(df)
    │                        │                        │
    │                        │                        ▼
    │                        │               factors/volume.py
    │                        │               compute_volume_factors(df)
    │                        │                        │
    │                        │                        ▼
    │                        │               factors/volatility.py
    │                        │               compute_volatility_factors(df)
    │                        │                        │
    │                        │                        ▼
    │                        │            labels/label_generator.py
    │                        │            generate_labels(df)  → 添加 label=0
    │                        │                        │
    │                        │                        ▼
    │                        │               dataset/builder.py
    │                        │               build_dataset(df)
    │                        │                        │
    │                        │                        ▼
    │                        │               dataset/scaler.py
    │                        │               scale_dataset(df)
    │                        │                        │
    └────────────────────────┴────────────────────────┘
                             │
                             ▼
                    io/exporter.py
                    export_factor_dataset(df, symbol)
                             │
                             ▼
              factor_pipeline/output/600000_factor.parquet
```

**`engine.py` 中的阶段顺序：**

1. 加载数据 — `load_snapshot()` + `load_market_data()`
2. 清洗数据 — `clean()`
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
python -m factor_pipeline.pipeline 600000
```

```bash
# 自定义快照目录与输出目录
python -m factor_pipeline.pipeline 600000 \
  --snapshot-dir data/market_data/snapshots/latest \
  --output-dir factor_pipeline/output
```

```bash
# 快照尚未发布时，直接指定日线目录
python -m factor_pipeline.pipeline 600000 \
  --daily-bars-dir data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d
```

预期输出：

```
[OK] saved -> factor_pipeline/output/600000_factor.parquet
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
pytest tests/test_factor_pipeline_loader.py -v
```

覆盖快照加载、股票代码补零、异常处理、导出路径，以及端到端引擎执行。

### 设计说明

- 沿用原 `feature_pipeline` 的快照输入约定（基于 manifest 加载）。
- **不**直接 import `market_data_pipeline`。
- **不**实现真实因子（MACD、RSI、动量等）、缩放（RobustScaler）或机器学习逻辑。
- `dataset/splitter.py` 预留给后续训练/验证/测试切分，尚未接入 `engine.py`。
