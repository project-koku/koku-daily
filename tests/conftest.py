"""Disposable databases only; no arbitrary connection URLs accepted."""

from pathlib import Path
import time

import pytest
from sqlalchemy import create_engine, text


def wait_replay(writer, reader):
    with writer.connect() as con:
        lsn = con.execute(text("SELECT pg_current_wal_lsn()::text")).scalar_one()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with reader.connect() as con:
            if con.execute(text("SELECT pg_last_wal_replay_lsn() >= CAST(:lsn AS pg_lsn)"), {"lsn": lsn}).scalar_one():
                return
        time.sleep(0.05)
    raise AssertionError("Local standby failed to replay fixture WAL")


@pytest.fixture
def pg():
    writer = create_engine("postgresql+psycopg2://postgres:local-test-only@127.0.0.1:25435/postgres")
    reader = create_engine("postgresql+psycopg2://postgres:local-test-only@127.0.0.1:25436/postgres")
    try:
        with writer.begin() as con:
            assert not con.execute(text("SELECT pg_is_in_recovery()")).scalar_one()
            with con.connection.cursor() as cursor:
                cursor.execute(Path("tests/fixtures/postgres.sql").read_text())
        with reader.connect() as con:
            assert con.execute(text("SELECT pg_is_in_recovery()")).scalar_one()
        wait_replay(writer, reader)
        yield writer, reader
    finally:
        writer.dispose()
        reader.dispose()
