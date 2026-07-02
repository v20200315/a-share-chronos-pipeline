# Feature Pipeline

## English Version

### Overview

`feature_pipeline` is the second subproject in the A-share Chronos data flow. It consumes standardized market data files and produces machine-learning-ready feature parquet files.

This subproject does not import or depend on `market_data_pipeline` code. The boundary between the two projects is the data contract on disk.

Version `v1` implements two technical indicators:

- MACD
- RSI

### Dependencies

This pipeline uses:

- TA-Lib for MACD and RSI
- Numba for feature post-processing helpers
- pandas, numpy, and pyarrow for parquet IO

After adding TA-Lib to `environment.yml`, update the Conda environment:

```bash
conda env update -n chronos_env -f environment.yml
```

### Input Contract

Preferred input:

```text
data/market_data/snapshots/latest/
  manifest.json
  daily_bars/<code>.parquet
```

The daily bar parquet must contain at least:

```text
code
date
close
```

If no snapshot has been published yet, pass the market-data daily bars directory explicitly:

```text
data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d/
```

### Output Contract

Default output:

```text
data/features/technical_indicators/version=v1/<code>.parquet
```

Output columns:

```text
code
date
close
macd
macd_signal
macd_hist
rsi
macd_rsi_valid
```

Leading warmup rows from MACD and RSI may contain NaN values and are preserved.

### Compute Features

Compute features from a published market-data snapshot:

```bash
python -m feature_pipeline.cli compute --symbols 000001,600000
```

Compute features directly from the market-data daily bars directory:

```bash
python -m feature_pipeline.cli compute \
  --symbols 000001,600000 \
  --daily-bars-dir data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d
```

### Boundary Rule

`feature_pipeline` should only read files from the previous layer. It should not import `market_data_pipeline.*` in production code.

## 中文版本

### 概览

`feature_pipeline` 是 A 股 Chronos 数据流中的第二个子项目。它消费标准化的行情数据文件，并产出机器学习可用的特征 parquet 文件。

这个子项目不导入也不依赖 `market_data_pipeline` 的代码。两个项目之间的边界是磁盘上的数据契约。

`v1` 版本只实现两个技术指标：

- MACD
- RSI

### 依赖

本流水线使用：

- TA-Lib 计算 MACD 和 RSI
- Numba 处理特征后处理辅助逻辑
- pandas、numpy、pyarrow 处理 parquet IO

把 TA-Lib 加入 `environment.yml` 后，更新 Conda 环境：

```bash
conda env update -n chronos_env -f environment.yml
```

### 输入契约

推荐输入：

```text
data/market_data/snapshots/latest/
  manifest.json
  daily_bars/<code>.parquet
```

日线 parquet 至少需要包含：

```text
code
date
close
```

如果还没有发布 snapshot，可以显式传入 market-data 日线目录：

```text
data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d/
```

### 输出契约

默认输出：

```text
data/features/technical_indicators/version=v1/<code>.parquet
```

输出字段：

```text
code
date
close
macd
macd_signal
macd_hist
rsi
macd_rsi_valid
```

MACD 和 RSI 前置 warmup 行可能包含 NaN，这些行会被保留。

### 计算特征

从已发布的 market-data snapshot 计算特征：

```bash
python -m feature_pipeline.cli compute --symbols 000001,600000
```

直接从 market-data 日线目录计算特征：

```bash
python -m feature_pipeline.cli compute \
  --symbols 000001,600000 \
  --daily-bars-dir data/market_data/daily_bars/provider=akshare/adjust=qfq/frequency=1d
```

### 边界规则

`feature_pipeline` 只应该读取上一层产出的文件。生产代码不应该导入 `market_data_pipeline.*`。