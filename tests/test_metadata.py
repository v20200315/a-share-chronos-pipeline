from market_data_pipeline.metadata.manager import MetadataManager


def test_refresh():
    m = MetadataManager()
    df = m.refresh()

    assert len(df) > 4000
    assert 'code' in df.columns
