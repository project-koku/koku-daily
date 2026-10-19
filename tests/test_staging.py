"""Lossless SQLite transport, exact arithmetic, rollback and disk lifetimes."""
from datetime import date
from decimal import Decimal, localcontext

import pytest
from kokudaily.staging import Store, fields


def test_lossless_columns_and_rollback(tmp_path):
    store = Store(tmp_path)
    try:
        store.create(
            "inputs",
            fields("amount numeric(33, 2), day date, raw jsonb, n bigint"),
        )
        values = [
            Decimal("-0.00"),
            Decimal("9999999999999999999999999999999.99"),
            None,
        ]
        with store.attempt():
            store.insert(
                "inputs",
                (
                    {
                        "amount": amount,
                        "day": date(2026, 10, 19),
                        "raw": raw,
                        "n": 2**63 - 1,
                    }
                    for amount, raw in zip(
                        values, [None, "null", '{"n":0.12345678901234567890}']
                    )
                ),
            )
        with pytest.raises(RuntimeError):
            with store.attempt():
                store.insert("inputs", [{"amount": Decimal("1.23")}])
                raise RuntimeError("retry")
        _, result = store.select(
            "SELECT * FROM inputs", store.schemas["inputs"]
        )
        rows = list(result)
        assert len(rows) == 3
        for expected, actual in zip(values, rows):
            assert actual["amount"] == expected
            if expected is not None:
                assert actual["amount"].as_tuple() == expected.as_tuple()
        assert [row["raw"] for row in rows] == [
            None,
            "null",
            '{"n":0.12345678901234567890}',
        ]
        assert rows[0]["day"] == date(2026, 10, 19)
        assert rows[0]["n"] == 2**63 - 1
    finally:
        path = store.path
        store.close()
    assert not path.exists()


def test_exact_aggregates_ignore_default_decimal_context(tmp_path):
    store = Store(tmp_path)
    try:
        store.create("numbers", {"n": "numeric(33, 2)"})
        with store.attempt():
            store.insert(
                "numbers",
                [
                    {"n": Decimal("9999999999999999999999999999999.99")},
                    {"n": Decimal("0.01")},
                    {"n": None},
                ],
            )
        with localcontext() as context:
            context.prec = 6
            assert (
                store.con.execute(
                    "SELECT decimal_sum(n) FROM numbers"
                ).fetchone()[0]
                == "10000000000000000000000000000000.00"
            )
            assert (
                store.con.execute(
                    "SELECT decimal_max(n) FROM numbers"
                ).fetchone()[0]
                == "9999999999999999999999999999999.99"
            )
        assert (
            store.con.execute(
                "SELECT decimal_sum(n) FROM numbers WHERE n IS NULL"
            ).fetchone()[0]
            is None
        )
        assert (
            store.con.execute("SELECT SUM(n) FROM numbers").fetchone()[0]
            == 1e31
        )
    finally:
        store.close()


def test_output_rows_repeat_without_materializing(tmp_path):
    store = Store(tmp_path)
    try:
        rows = store.output(
            "output", ["n"], ({"n": Decimal(f"{i}.00")} for i in range(1000))
        )
        assert len(rows) == 1000
        assert next(iter(rows)) == {"n": Decimal("0.00")}
        assert next(iter(rows)) == {"n": Decimal("0.00")}
        from itertools import islice

        assert list(islice(rows, 999, 1000)) == [{"n": Decimal("999.00")}]
    finally:
        store.close()


def test_stream_failure_rolls_back_before_retry_and_closes_reader(
    tmp_path, monkeypatch
):
    from kokudaily.replica import read_to_store, retry_read
    from test_replica import Engine, Result, conflict

    class Partial(Result):
        def mappings(self):
            yield {"amount": Decimal("1.23")}
            raise conflict()

    class Reader(Engine):
        def execute(self, sql, params=None):
            if str(sql).startswith("SET "):
                return super().execute(sql, params)
            result = next(self.results)
            return result

    reader = Reader([Partial([]), Result([{"amount": Decimal("2.34")}])])
    pauses = []
    import kokudaily.replica as replica

    monkeypatch.setattr(
        replica.time, "sleep", lambda delay: pauses.append(reader.active)
    )
    with Store(tmp_path) as store:
        store.create("inputs", {"amount": "numeric(33, 2)"})
        retry_read(
            lambda: read_to_store(reader, "SELECT amount", store, "inputs"),
            delay=0,
        )
        _, rows = store.select("SELECT * FROM inputs", store.schemas["inputs"])
        assert list(rows) == [{"amount": Decimal("2.34")}]
        assert pauses == [False]
        assert reader.events.count("rollback") == 1
        assert reader.events.count("close") == 2


def test_missing_directory_fails_without_fallback(tmp_path):
    with pytest.raises(FileNotFoundError):
        Store(tmp_path / "missing")


def test_sqlite_full_rolls_back_without_partial_output(tmp_path):
    import sqlite3

    with Store(tmp_path) as store:
        store.create("inputs", {"payload": "text"})
        store.con.execute("PRAGMA max_page_count=4")
        with pytest.raises(sqlite3.OperationalError, match="full"):
            with store.attempt():
                store.insert("inputs", [{"payload": "x" * 100000}])
        assert (
            store.con.execute("SELECT count(*) FROM inputs").fetchone()[0] == 0
        )


def test_float_cannot_silently_enter_exact_numeric_column(tmp_path):
    with Store(tmp_path) as store:
        store.create("costs", {"amount": "numeric(33, 2)"})
        with pytest.raises(TypeError, match="Floating-point"):
            with store.attempt():
                store.insert("costs", [{"amount": 0.1}])
        assert (
            store.con.execute("SELECT count(*) FROM costs").fetchone()[0] == 0
        )


def test_nested_output_types_and_unsupported_object(tmp_path):
    from datetime import datetime, timezone
    from uuid import UUID

    value = {
        "decimal": Decimal("-0.00"),
        "day": date(2026, 10, 19),
        "timestamp": datetime(2026, 10, 19, tzinfo=timezone.utc),
        "identifier": UUID(int=1),
        "bytes": b"raw",
        "array": [None, 1, "null"],
        "object": {"truth": True},
    }
    with Store(tmp_path) as store:
        rows = store.output("typed", list(value), [value])
        assert rows == [value]
        assert (
            next(iter(rows))["decimal"].as_tuple()
            == value["decimal"].as_tuple()
        )
        with pytest.raises(
            TypeError, match="Unsupported report value type: object"
        ):
            with store.attempt():
                store.output("invalid", ["value"], [{"value": object()}])
    store.close()  # Closing twice is safe.


def test_numeric_nan_and_null_max(tmp_path):
    with Store(tmp_path) as store:
        store.create("values_table", {"amount": "numeric"})
        with store.attempt():
            store.insert(
                "values_table",
                [
                    {"amount": None},
                    {"amount": Decimal("NaN")},
                    {"amount": Decimal("1.00")},
                ],
            )
        assert store.con.execute(
            "SELECT decimal_sum(amount), decimal_max(amount) FROM values_table"
        ).fetchone() == ("NaN", "NaN")
        assert (
            store.con.execute(
                "SELECT decimal_max(amount) FROM values_table WHERE amount IS NULL"
            ).fetchone()[0]
            is None
        )


def test_failed_sqlite_open_removes_run_directory(tmp_path, monkeypatch):
    import sqlite3
    import kokudaily.staging as staging

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("cannot open scratch")

    monkeypatch.setattr(staging.sqlite3, "connect", fail)
    with pytest.raises(sqlite3.OperationalError, match="cannot open"):
        Store(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_missing_schema_stream_does_not_execute_source(tmp_path):
    from kokudaily.replica import read_to_store
    from test_replica import Engine

    engine = Engine([[]])
    with Store(tmp_path) as store:
        store.create("inputs", {"value": "text"})
        assert (
            read_to_store(
                engine,
                "SELECT value FROM org1.source",
                store,
                "inputs",
                schema="org1",
            )
            == []
        )
        assert (
            store.con.execute("SELECT count(*) FROM inputs").fetchone()[0] == 0
        )
    assert not any("org1.source" in str(event) for event in engine.events)
