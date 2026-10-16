"""Behavioral contracts for replica computation and bounded final writes."""

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from kokudaily import replica
from sqlalchemy.exc import DBAPIError


class Result:
    def __init__(self, rows):
        self.rows = rows

    def keys(self):
        return list(self.rows[0]) if self.rows else []

    def mappings(self):
        return self.rows

    def __iter__(self):
        return iter(tuple(row.values()) for row in self.rows)


class Engine:
    def __init__(self, results=()):
        self.results = iter(results)
        self.events = []
        self.active = False

    @contextmanager
    def connect(self):
        self.events.append("connect")
        try:
            yield self
        finally:
            self.events.append("close")

    @contextmanager
    def begin(self):
        self.active = True
        self.events.append("begin")
        try:
            yield self
        except Exception:
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")
        finally:
            self.active = False

    def execute(self, sql, params=None):
        self.events.append((str(sql), params))
        if str(sql).startswith(("SET ", "SELECT set_config")):
            return None
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return Result(result)


def conflict(
    code="40001", message="canceling statement due to conflict with recovery"
):
    original = Exception(message)
    original.pgcode = code
    original.diag = SimpleNamespace(message_primary=message)
    return DBAPIError("query", {}, original)


def test_reads_are_read_only_fully_consumed_and_committed():
    engine = Engine([[{"amount": Decimal("1.23")}]])
    result = replica.read_rows(engine, "SELECT amount FROM org1.cost")
    assert result.rows == [{"amount": Decimal("1.23")}]
    assert result.columns == ["amount"]
    assert engine.events == [
        "connect",
        "begin",
        ("SET TRANSACTION READ ONLY", None),
        ("SELECT amount FROM org1.cost", {}),
        "commit",
        "close",
    ]
    assert not engine.active


@pytest.mark.parametrize("code", ["40001", "57014", "57P01"])
def test_conflict_rolls_back_before_retry_and_publishes_once(
    monkeypatch, code
):
    engine = Engine([conflict(code), [{"x": 2}]])
    pauses = []
    monkeypatch.setattr(
        replica.time,
        "sleep",
        lambda delay: pauses.append((delay, engine.active)),
    )
    result = replica.read_schema(
        engine, "SELECT 2 AS x", "org1", {}, delay=0.1
    )
    assert result.rows == [{"x": 2}]
    assert result.complete
    assert engine.events.count("rollback") == 1
    assert engine.events.count("commit") == 1
    assert engine.events.count("connect") == 2
    assert pauses == [(0.1, False)]


def test_exhausted_conflicts_are_explicit_and_bounded(monkeypatch, caplog):
    engine = Engine([conflict(), conflict(), conflict()])
    monkeypatch.setattr(replica.time, "sleep", Mock())
    result = replica.read_schema(engine, "SELECT 1", "org1", {}, delay=0)
    assert not result.complete
    assert result.rows == []
    assert engine.events.count("rollback") == 3
    assert "org1" in caplog.text and "incomplete" in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        conflict("40001", "serialization failure"),
        conflict("57014", "canceling statement due to user request"),
        RuntimeError("offline"),
    ],
)
def test_unrelated_errors_propagate_without_retry(error):
    engine = Engine([error])
    with pytest.raises(type(error)):
        replica.read_schema(engine, "SELECT 1", "org1", {})
    assert engine.events.count("rollback") == 1


def test_missing_schema_is_checked_in_same_short_transaction():
    engine = Engine([[]])
    result = replica.read_schema(
        engine, "SELECT 1 FROM {schema}.cost", "org1", {}, check_exists=True
    )
    assert result.complete and result.rows == []
    assert engine.events.count("commit") == 1
    assert not any("org1.cost" in str(event) for event in engine.events)


def test_unsafe_schema_rejected_before_connect():
    engine = Engine()
    with pytest.raises(ValueError):
        replica.read_schema(engine, "SELECT 1", "org1; DROP SCHEMA public", {})
    assert engine.events == []


def test_history_overlay_replaces_dates_without_losing_precision():
    old = [
        {"date": date(2026, 1, 1), "amount": None},
        {"date": date(2026, 2, 1), "amount": Decimal("1.11")},
    ]
    current = [
        {
            "date": date(2026, 2, 1),
            "amount": Decimal("12345678901234567890.12"),
        }
    ]
    assert replica.merge_history(old, current) == [old[0], current[0]]
    assert old[1]["amount"] == Decimal("1.11")


def test_intermediates_are_bound_and_preserve_numeric_and_null():
    sql, params = replica.bind_datasets(
        "SELECT * FROM __test",
        {"__test": [{"amount": Decimal("1.23"), "other": None}]},
        {"__test": "amount numeric(33, 2), other text"},
    )
    assert "jsonb_to_recordset" in sql
    assert "1.23" not in sql
    assert '"1.23"' in params["dataset_0"]
    assert "null" in params["dataset_0"]


def test_all_final_totals_commit_once_with_local_timeouts():
    engine = Engine([[], [], []])
    rows = [{"date": day} for day in range(201)]
    replica.write_totals(engine, "INSERT final VALUES (:date)", rows)
    inserts = [
        e
        for e in engine.events
        if isinstance(e, tuple) and e[0].startswith("INSERT")
    ]
    assert [len(e[1]) for e in inserts] == [201]
    assert engine.events.count("commit") == 1
    assert engine.events.count("begin") == 1
    settings = [
        e
        for e in engine.events
        if isinstance(e, tuple) and "set_config" in e[0]
    ]
    assert len(settings) == 2
    assert {e[1]["timeout"] for e in settings} == {"5000ms", "1000ms"}


def test_failed_final_write_rolls_back_and_propagates():
    engine = Engine([RuntimeError("locked")])
    with pytest.raises(RuntimeError, match="locked"):
        replica.write_totals(engine, "INSERT final", [{"date": 1}])
    assert engine.events[-1] == "rollback"


def test_no_rows_never_opens_writer():
    engine = Engine()
    replica.write_totals(engine, "INSERT final", [])
    assert engine.events == []


def test_all_totals_use_one_statement_so_timeout_covers_whole_write():
    engine = Engine([[]])
    replica.write_totals(
        engine,
        "INSERT final (date) VALUES (:date)",
        [{"date": 1}, {"date": 2}],
    )
    inserts = [
        event
        for event in engine.events
        if isinstance(event, tuple) and event[0].startswith("INSERT")
    ]
    assert len(inserts) == 1
    assert isinstance(inserts[0][1], dict)
    assert sorted(inserts[0][1].values()) == [1, 2]


@pytest.mark.parametrize(
    "options", [{"attempts": 0}, {"delay": -1}, {"delay": float("nan")}]
)
def test_invalid_retry_settings_never_connect(options):
    engine = Engine()
    with pytest.raises(ValueError, match="retry settings"):
        replica.read_schema(engine, "SELECT 1", "org1", {}, **options)
    assert not engine.events


@pytest.mark.parametrize(
    "options",
    [{"statement_timeout": 0}, {"lock_timeout": -1}],
)
def test_invalid_writer_settings_never_connect(options):
    engine = Engine()
    with pytest.raises(ValueError, match="must be positive"):
        replica.write_totals(engine, "INSERT final", [], **options)
    assert not engine.events


def test_malformed_totals_upsert_rolls_back():
    engine = Engine()
    with pytest.raises(ValueError, match="VALUES clause"):
        replica.write_totals(engine, "INSERT final", [{"x": 1}, {"x": 2}])
    assert engine.events == [
        "begin",
        (
            "SELECT set_config('statement_timeout', :timeout, true)",
            {"timeout": "5000ms"},
        ),
        (
            "SELECT set_config('lock_timeout', :timeout, true)",
            {"timeout": "1000ms"},
        ),
        "rollback",
    ]


def test_intermediate_serialization_rejects_unsupported_types_without_repr():
    with pytest.raises(
        TypeError, match="Unsupported report value type: object"
    ):
        replica.bind_datasets(
            "SELECT * FROM __test",
            {"__test": [{"value": object()}]},
            {"__test": "value text"},
        )


def test_intermediate_uuid_and_timestamp_round_trip():
    import json
    from datetime import datetime, timezone
    from uuid import UUID

    value = UUID("00000000-0000-0000-0000-000000000001")
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _, parameters = replica.bind_datasets(
        "SELECT * FROM __test",
        {"__test": [{"id": value, "created": timestamp}]},
        {"__test": "id uuid, created timestamptz"},
    )
    assert json.loads(parameters["dataset_0"]) == [
        {"id": str(value), "created": timestamp.isoformat()}
    ]


@pytest.mark.parametrize("code", ["40001", "57014", "57P01"])
def test_general_read_retries_after_rollback_and_close(monkeypatch, code):
    engine = Engine([conflict(code), [{"count": 2}]])
    pauses = []
    monkeypatch.setattr(
        replica.time,
        "sleep",
        lambda delay: pauses.append(
            (delay, list(engine.events), engine.active)
        ),
    )
    result = replica.retry_read(
        lambda: replica.read_rows(engine, "SELECT count(*)"),
        attempts=2,
        delay=0.25,
    )
    assert result.rows == [{"count": 2}]
    assert len(pauses) == 1
    assert pauses[0][0] == 0.25
    assert pauses[0][1][-2:] == ["rollback", "close"]
    assert pauses[0][2] is False
    assert engine.events.count("connect") == 2
    assert engine.events.count("commit") == 1


def test_general_read_exhaustion_reraises_last_error(monkeypatch):
    errors = [conflict(), conflict()]
    engine = Engine(errors)
    sleep = Mock()
    monkeypatch.setattr(replica.time, "sleep", sleep)
    with pytest.raises(DBAPIError) as caught:
        replica.retry_read(
            lambda: replica.read_rows(engine, "SELECT 1"),
            attempts=2,
            delay=0.25,
        )
    assert caught.value is errors[-1]
    assert engine.events.count("rollback") == 2
    assert engine.events.count("close") == 2
    sleep.assert_called_once_with(0.25)


@pytest.mark.parametrize(
    "error",
    [
        conflict("57014", "canceling statement due to user request"),
        conflict("40001", "serialization failure"),
        RuntimeError("offline"),
    ],
)
def test_general_read_unrelated_failure_never_retries(monkeypatch, error):
    operation = Mock(side_effect=error)
    sleep = Mock()
    monkeypatch.setattr(replica.time, "sleep", sleep)
    with pytest.raises(type(error)) as caught:
        replica.retry_read(operation)
    assert caught.value is error
    operation.assert_called_once_with()
    sleep.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        {"attempts": 0},
        {"delay": -1},
        {"delay": float("nan")},
    ],
)
def test_general_read_invalid_settings_never_calls_operation(options):
    operation = Mock()
    with pytest.raises(ValueError, match="retry settings"):
        replica.retry_read(operation, **options)
    operation.assert_not_called()
