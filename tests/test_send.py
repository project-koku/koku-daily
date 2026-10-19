"""Streaming delivery preserves CSV-to-Parquet behavior and run cleanup."""
from unittest.mock import Mock

import pyarrow.csv as arrow_csv
import pyarrow.parquet as parquet
import pytest
from kokudaily import send
from kokudaily.staging import ReportBundle, Store


@pytest.mark.parametrize(
    "content",
    [
        "value,label\n",
        "value,label\n1,a\n,b\n3,c\n",
        "time,stamp,flag,text\n12:34:56,2026-10-19T12:34:56.123Z,true,plain\n",
        'stamp,text\n2026-10-19T12:34:56.123,"a,b"\n',
    ],
)
def test_s3_streamed_parquet_matches_previous_conversion(
    tmp_path, monkeypatch, content
):
    source = tmp_path / "report.csv"
    source.write_text(content)
    client = Mock()
    client.bucket_exists.return_value = True
    monkeypatch.setattr(send, "get_minio_client", lambda: client)
    monkeypatch.setattr(send.Config, "MINIO_ACCESS_KEY", "test-only")
    monkeypatch.setattr(send.Config, "MINIO_BUCKET", "test-only")
    send.s3("marketing", "report", file=str(source))
    expected_table = arrow_csv.read_csv(source)
    assert send._parquet_types(source) == {
        field.name: field.type for field in expected_table.schema
    }
    parquet.write_table(expected_table, tmp_path / "legacy.parquet")
    actual = parquet.read_table(tmp_path / "report.parquet")
    assert actual.equals(parquet.read_table(tmp_path / "legacy.parquet"))
    client.fput_object.assert_called_once()


def test_bundle_cleans_scratch_after_delivery_failure(tmp_path):
    store = Store(tmp_path)
    path = store.directory.name
    with pytest.raises(RuntimeError, match="delivery"):
        with ReportBundle(store):
            raise RuntimeError("delivery failed")
    from pathlib import Path

    assert not Path(path).exists()


@pytest.mark.parametrize(
    "prefix,suffix",
    [
        ("", "1"),
        ("1", "1.5"),
        ("1", "true"),
        ("2026-10-19", "2026-10-19T12:34:56.123Z"),
        (" 1", " 2.5"),
    ],
)
def test_streaming_parquet_preserves_types_across_csv_blocks(
    tmp_path, monkeypatch, prefix, suffix
):
    path = tmp_path / "changing.csv"
    path.write_text(
        "value,label\n" + (prefix + ",a\n") * 400000 + suffix + ",a\n"
    )
    client = Mock()
    client.bucket_exists.return_value = True
    monkeypatch.setattr(send, "get_minio_client", lambda: client)
    monkeypatch.setattr(send.Config, "MINIO_ACCESS_KEY", "test-only")
    monkeypatch.setattr(send.Config, "MINIO_BUCKET", "test-only")
    expected = arrow_csv.read_csv(path)
    send.s3("marketing", "changing", file=str(path))
    assert parquet.read_table(tmp_path / "changing.parquet").equals(expected)
