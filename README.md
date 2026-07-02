# A-Share Chronos Pipeline

## English Version

### Overview

`a-share-chronos-pipeline` is an industrial-grade A-share AI data pipeline. It is not a single quantitative trading strategy. Its goal is to build a layered data production system where each stage owns one part of the data flow and communicates with the next stage through stable data contracts.

The pipeline is organized into four subprojects:

| Subproject | Responsibility | Input | Output |
| --- | --- | --- | --- |
| `market_data_pipeline` | Data ingestion | EastMoney, AkShare, exchange APIs, raw provider data | Raw Parquet market data |
| `feature_pipeline` | Feature engineering | Raw Parquet | Feature Parquet with technical indicators and labels |
| `model_pipeline` | AI model training | Feature Parquet | Trained models, predictions, feature importance |
| `backtest_pipeline` | Backtesting and evaluation | Predictions and price data | Backtest reports, equity curves, performance metrics |

The full pipeline is:

```text
Market Data -> Feature -> Model -> Backtest
```

### Environment

The Conda environment is defined in `environment.yml` and is named `chronos_env`.

Create the environment for the first time:

```bash
conda env create -f environment.yml
conda activate chronos_env
```

If you add a dependency to `environment.yml`, update the existing environment:

```bash
conda env update -n chronos_env -f environment.yml
```

Use `--prune` only when you want Conda to remove packages that are no longer listed in `environment.yml`:

```bash
conda env update -n chronos_env -f environment.yml --prune
```

After adding a package such as Streamlit, verify it from `chronos_env`:

```bash
python -c "import streamlit; print(streamlit.__version__)"
```

### Pipeline Architecture

```text
EastMoney / AkShare / APIs
        |
        v
01 Market Data Pipeline
        |
        | Raw Parquet
        v
02 Feature Pipeline
        |
        | Feature Parquet
        v
03 Model Pipeline
        |
        | Prediction
        v
04 Backtest Pipeline
```

### 01 Market Data Pipeline

The market data layer converts the exchange and provider world into a unified local data format.

Inputs:

- EastMoney
- AkShare
- Tushare, optional
- exchange data
- announcements
- indexes
- ETFs

Outputs:

```text
metadata.parquet
daily/<symbol>.parquet
minute/
adjust_factor/
calendar/
```

This layer should not know anything about LightGBM, Backtrader, or feature engineering internals. It only produces standardized raw market data.

See `market_data_pipeline/README.md` for detailed usage.

### 02 Feature Pipeline

The feature layer transforms raw market data into machine-learning-ready features and labels.

Inputs:

- daily parquet
- adjust factors
- trading calendar

Outputs:

```text
feature.parquet
```

Typical columns:

- `date`
- `symbol`
- `close`
- `volume`
- technical indicators such as `MA5`, `MA10`, `MACD`, `RSI`, `ATR`
- labels

Typical processing:

```text
Raw Data -> Cleaning -> Forward Adjust -> TA-Lib -> Numba -> Features -> Labels
```

This layer should not know anything about Backtrader or the model implementation.

### 03 Model Pipeline

The model layer is responsible only for machine learning.

Inputs:

- `feature.parquet`

Outputs:

```text
model.bin
prediction.parquet
feature_importance.csv
best_params.json
```

Typical processing:

```text
Features -> TimeSeriesSplit -> Optuna -> LightGBM -> Prediction
```

This layer should not know where the original market data came from.

### 04 Backtest Pipeline

The backtest layer validates model predictions as trading signals.

Inputs:

- `prediction.parquet`
- raw price data

Outputs:

```text
equity_curve.html
trade.csv
performance.json
report.pdf
```

Typical processing:

```text
Prediction -> Signal -> Backtrader -> Portfolio -> Performance
```

This layer should not know how features were generated.

### Data Contracts

The most important rule is that the four layers should not depend on each other's internal code. Each layer should depend only on the standardized output data from the previous layer.

```text
01 Market Data Pipeline
        |
        | Raw Parquet
        v
02 Feature Pipeline
        |
        | Feature Parquet
        v
03 Model Pipeline
        |
        | Prediction
        v
04 Backtest Pipeline
```

This means:

- `market_data_pipeline` does not know about LightGBM.
- `feature_pipeline` does not know about Backtrader.
- `model_pipeline` does not know about EastMoney.
- `backtest_pipeline` does not know about TA-Lib.

This design keeps data sources, feature logic, model algorithms, and backtest frameworks independently replaceable.

### Naming

This repository currently uses Python package names with underscores:

```text
market_data_pipeline/
feature_pipeline/
model_pipeline/
backtest_pipeline/
```

Use these names for Python imports and `python -m` commands. In human-facing documentation, the subprojects can be referred to as Market Data Pipeline, Feature Pipeline, Model Pipeline, and Backtest Pipeline.

## 中文版本

### 概览

`a-share-chronos-pipeline` 是一个工业级 A 股 AI 数据流水线工程。它不是一个单一量化策略，而是一个分层的数据生产系统。每一层只负责数据流中的一个阶段，并通过稳定的数据契约把结果交给下一层。

整个工程包含四个子项目：

| 子项目 | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| `market_data_pipeline` | 数据采集 | 东方财富、AkShare、交易所 API、原始 provider 数据 | 原始 Parquet 行情数据 |
| `feature_pipeline` | 特征工程 | Raw Parquet | 带技术指标和标签的 Feature Parquet |
| `model_pipeline` | AI 模型训练 | Feature Parquet | 训练好的模型、预测结果、特征重要性 |
| `backtest_pipeline` | 回测与评估 | Prediction 和价格数据 | 回测报告、资金曲线、绩效指标 |

完整流水线是：

```text
Market Data -> Feature -> Model -> Backtest
```

### 环境

Conda 环境由 `environment.yml` 定义，环境名是 `chronos_env`。

第一次创建环境：

```bash
conda env create -f environment.yml
conda activate chronos_env
```

如果在 `environment.yml` 中新增依赖，更新已有环境：

```bash
conda env update -n chronos_env -f environment.yml
```

只有当你希望 Conda 删除 `environment.yml` 中已经不再列出的包时，才使用 `--prune`：

```bash
conda env update -n chronos_env -f environment.yml --prune
```

新增 Streamlit 这类包之后，可以在 `chronos_env` 中验证：

```bash
python -c "import streamlit; print(streamlit.__version__)"
```

### 流水线架构

```text
东方财富 / AkShare / APIs
        |
        v
01 Market Data Pipeline
        |
        | Raw Parquet
        v
02 Feature Pipeline
        |
        | Feature Parquet
        v
03 Model Pipeline
        |
        | Prediction
        v
04 Backtest Pipeline
```

### 01 Market Data Pipeline

市场数据层负责把交易所和数据源世界转换成统一的本地数据格式。

输入：

- 东方财富
- AkShare
- Tushare，可选
- 交易所数据
- 公告
- 指数
- ETF

输出：

```text
metadata.parquet
daily/<symbol>.parquet
minute/
adjust_factor/
calendar/
```

这一层不应该知道 LightGBM、Backtrader 或特征工程内部逻辑。它只负责生产标准化的原始行情数据。

详细用法见 `market_data_pipeline/README.md`。

### 02 Feature Pipeline

特征层负责把原始行情数据转换成机器学习可用的特征和标签。

输入：

- 日线 parquet
- 复权因子
- 交易日历

输出：

```text
feature.parquet
```

典型字段：

- `date`
- `symbol`
- `close`
- `volume`
- 技术指标，例如 `MA5`、`MA10`、`MACD`、`RSI`、`ATR`
- 标签

典型处理流程：

```text
Raw Data -> Cleaning -> Forward Adjust -> TA-Lib -> Numba -> Features -> Labels
```

这一层不应该知道 Backtrader 或模型实现细节。

### 03 Model Pipeline

模型层只负责机器学习。

输入：

- `feature.parquet`

输出：

```text
model.bin
prediction.parquet
feature_importance.csv
best_params.json
```

典型处理流程：

```text
Features -> TimeSeriesSplit -> Optuna -> LightGBM -> Prediction
```

这一层不应该知道原始行情数据来自哪里。

### 04 Backtest Pipeline

回测层负责把模型预测结果作为交易信号进行验证。

输入：

- `prediction.parquet`
- 原始价格数据

输出：

```text
equity_curve.html
trade.csv
performance.json
report.pdf
```

典型处理流程：

```text
Prediction -> Signal -> Backtrader -> Portfolio -> Performance
```

这一层不应该知道特征是如何生成的。

### 数据契约

整个工程最重要的原则是：四层之间不要依赖彼此的内部代码，只依赖上一层的标准化输出数据。

```text
01 Market Data Pipeline
        |
        | Raw Parquet
        v
02 Feature Pipeline
        |
        | Feature Parquet
        v
03 Model Pipeline
        |
        | Prediction
        v
04 Backtest Pipeline
```

也就是说：

- `market_data_pipeline` 不知道 LightGBM 的存在。
- `feature_pipeline` 不知道 Backtrader 的存在。
- `model_pipeline` 不知道东方财富的存在。
- `backtest_pipeline` 不知道 TA-Lib 的存在。

这种设计可以让数据源、特征逻辑、模型算法和回测框架独立替换和演进。

### 命名

当前仓库使用带下划线的 Python 包名：

```text
market_data_pipeline/
feature_pipeline/
model_pipeline/
backtest_pipeline/
```

这些名称用于 Python import 和 `python -m` 命令。在面向人的文档中，可以称为 Market Data Pipeline、Feature Pipeline、Model Pipeline 和 Backtest Pipeline。
