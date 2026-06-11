# A-Share Chronos Pipeline 
# A股时序量化数据蓄水池工程

## Metadata CLI

Refresh A-share metadata from AkShare:

```bash
python -m chronos_pipeline.cli refresh --provider akshare
```

Refresh A-share metadata from EastMoney:

```bash
python -m chronos_pipeline.cli refresh --provider eastmoney
```

Load the generated AkShare metadata parquet:

```bash
python -m chronos_pipeline.cli load --provider akshare
```

Load the generated EastMoney metadata parquet:

```bash
python -m chronos_pipeline.cli load --provider eastmoney
```