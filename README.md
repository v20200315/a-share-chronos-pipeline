# A-Share Chronos Pipeline 
# A股时序量化数据蓄水池工程

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
python -m chronos_pipeline.cli refresh --provider akshare
python -m chronos_pipeline.cli refresh --provider eastmoney
```

Output files:

- `data/metadata/stock_basic_akshare.parquet`
- `data/metadata/stock_basic_eastmoney.parquet`

### 2. Validate Metadata

Validate checks the saved parquet and writes a validation report.

```bash
python -m chronos_pipeline.cli validate --provider akshare
python -m chronos_pipeline.cli validate --provider eastmoney
```

Validation reports are written under:

```text
data/metadata/audit/<provider>/
```

Use strict mode if warnings should fail validation:

```bash
python -m chronos_pipeline.cli validate --provider akshare --strict
python -m chronos_pipeline.cli validate --provider eastmoney --strict
```

### 3. Preview Cleanup

Run cleanup in dry-run mode first. This shows how many rows would be removed, but does not modify the parquet file.

```bash
python -m chronos_pipeline.cli clean --provider akshare --dry-run
python -m chronos_pipeline.cli clean --provider eastmoney --dry-run
```

Add `--strict` if warning-level row issues should also be removed, such as missing `list_date`.

```bash
python -m chronos_pipeline.cli clean --provider akshare --strict --dry-run
python -m chronos_pipeline.cli clean --provider eastmoney --strict --dry-run
```

Example output:

```text
[INFO] cleanup: before=5532, after=5531, removed=1
[INFO] dry-run: parquet not modified
```

### 4. Apply Cleanup

If the dry-run result looks correct, run cleanup without `--dry-run`.

```bash
python -m chronos_pipeline.cli clean --provider akshare
python -m chronos_pipeline.cli clean --provider eastmoney
```

Use strict cleanup only when you intentionally want to remove warning-level row issues.

```bash
python -m chronos_pipeline.cli clean --provider akshare --strict
python -m chronos_pipeline.cli clean --provider eastmoney --strict
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
python -m chronos_pipeline.cli validate --provider akshare
python -m chronos_pipeline.cli validate --provider eastmoney
```

### 5. Load Metadata

Print the first rows of the saved parquet:

```bash
python -m chronos_pipeline.cli load --provider akshare
python -m chronos_pipeline.cli load --provider eastmoney
```