
import pandas as pd


class MetadataValidator:
    @staticmethod
    def validate_stock_basic(df: pd.DataFrame):

        # 1. 基础规模
        assert 4000 < len(df) < 6500, f'异常行数: {len(df)}'

        # 2. code唯一性
        assert df['code'].is_unique, 'code重复'

        # 3. 空值
        assert df['code'].notna().all()
        assert df['name'].notna().all()

        # 4. 格式
        assert df['code'].astype(str).str.match(r'^\d{6}$').all()

        # 5. exchange
        assert df['exchange'].isin(['SH', 'SZ', 'BJ', 'A']).all()

        # 6. status
        assert df['status'].isin(['LISTED', 'UNKNOWN', 'DELISTED']).all()

        # 7. list_date（如果存在）
        if 'list_date' in df.columns:
            df['list_date'] = pd.to_datetime(df['list_date'], errors='coerce')

        print('✅ Data validation passed')
