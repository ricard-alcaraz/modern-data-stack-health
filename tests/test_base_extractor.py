import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from ingestion.extractors.base_extractor import BaseExtractor

class DummyExtractor(BaseExtractor):
    def extract(self):
        pass

def test_get_latest_timestamp_from_warehouse_defaults_when_no_writer():
    ext = DummyExtractor("owner", "repo", "/tmp", db_writer=None)
    # Should return a timezone-aware datetime object ~90 days ago
    ts = ext._get_latest_timestamp_from_warehouse("my_table")
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None

def test_get_latest_timestamp_from_warehouse_handles_iso_string_with_z():
    mock_writer = MagicMock()
    mock_writer.conn.execute().fetchone.return_value = ("2024-01-01T12:00:00Z",)
    
    ext = DummyExtractor("owner", "repo", "/tmp", db_writer=mock_writer)
    ts = ext._get_latest_timestamp_from_warehouse("my_table")
    
    assert isinstance(ts, datetime)
    assert ts.year == 2024
    assert ts.tzinfo is not None

def test_get_latest_timestamp_from_warehouse_handles_naive_db_datetime():
    mock_writer = MagicMock()
    # Simulate a naive datetime returned by some DB drivers
    naive_dt = datetime(2024, 1, 1, 12, 0, 0)
    mock_writer.conn.execute().fetchone.return_value = (naive_dt,)
    
    ext = DummyExtractor("owner", "repo", "/tmp", db_writer=mock_writer)
    ts = ext._get_latest_timestamp_from_warehouse("my_table")
    
    assert isinstance(ts, datetime)
    assert ts.tzinfo == timezone.utc # Should be converted to UTC
    
def test_get_latest_timestamp_uses_safe_identifier():
    mock_writer = MagicMock()
    ext = DummyExtractor("owner", "repo", "/tmp", db_writer=mock_writer)
    
    # Should raise ValueError from safe_identifier before executing the query
    with pytest.raises(ValueError):
        ext._get_latest_timestamp_from_warehouse("table; DROP TABLE users")