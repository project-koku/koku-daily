"""SQL parity, real standby execution, and recovery/locking behavior."""

import csv
import threading
import time
from collections import Counter
from copy import deepcopy
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import pytest
from conftest import wait_replay
from kokudaily import reports
from kokudaily.replica import is_recovery_conflict
from kokudaily.replica import read_rows
from kokudaily.replica import read_schema
from kokudaily.replica import retry_read
from kokudaily.replica import write_totals
from kokudaily.setup_runner import list_tenant_schemas
from kokudaily.setup_runner import render_schema_sql
from sqlalchemy import event
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

LEGACY = Path("tests/fixtures/legacy_sql")
FROZEN_SQL = frozenset(
    {
        "cust_cost_model_report_setup_schema.sql",
        "cust_node_report_setup_schema.sql",
        "cust_tag_report.sql",
        "cust_tag_report_setup_schema.sql",
        "key_metrics/cust_cloud_costs_data_setup_schema.sql",
        "key_metrics/cust_openshift_costs_data_setup_schema.sql",
        "key_metrics/cust_openshift_infra_data_setup_schema.sql",
        "key_metrics/cust_total_data.sql",
        "key_metrics/cust_total_data_setup.sql",
    }
)


def legacy_sql(name):
    """Freeze modified SQL; share queries unchanged by COST-8395."""
    root = LEGACY if name in FROZEN_SQL else Path("kokudaily/sql")
    return (root / name).read_text()


def configure(monkeypatch, reader, writer, tmp_path):
    monkeypatch.setattr(reports, "DB_ENGINE", writer)
    monkeypatch.setattr(reports, "create_engine", lambda readonly: reader)
    monkeypatch.setattr(reports.Config, "NAMESPACE", "hccm-prod")
    monkeypatch.setattr(reports.Config, "RUN_DAILY_REPORTS", True)
    monkeypatch.setattr(
        reports.Config,
        "WEEKLY_REPORT_SCHEDULED_DAY",
        datetime.now(timezone.utc).weekday(),
    )
    monkeypatch.setattr(reports, "gettempdir", lambda: str(tmp_path))
    tasks = deepcopy(reports.REQUIRES)
    start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    for task in tasks[0]["setup"]:
        task["sql_parameters"] = dict(
            task.get("sql_parameters") or {}, start_time=start
        )
    monkeypatch.setattr(reports, "REQUIRES", tasks)


def legacy_outputs(writer):
    expected = {}
    with writer.connect() as con:
        cutoff = con.execute(text("SELECT clock_timestamp()")).scalar_one()
        for task in reports.REQUIRES[0]["setup"]:
            params = dict(task["sql_parameters"], run_cutoff=cutoff)
            if "per_schema_file" in task:
                con.execute(text(legacy_sql(task["init_file"][4:])))
                for schema in list_tenant_schemas(
                    con, task["tenant_filter"], params.get("provider_types")
                ):
                    sql = legacy_sql(task["per_schema_file"][4:])
                    con.execute(
                        text(render_schema_sql(sql, schema)),
                        dict(params, customer=schema),
                    )
            else:
                con.execute(text(legacy_sql(task["file"][4:])))
        selected = dict(
            reports.REPORTS, **reports.WEEKLY_REPORTS, **reports.DAILY_REPORTS
        )
        for name, report in selected.items():
            if report.get("namespace", "hccm-prod") != "hccm-prod":
                continue
            sql = legacy_sql(report["file"][4:])
            result = con.execute(text(sql), report.get("sql_parameters") or {})
            expected[name] = (list(result.keys()), list(result.fetchall()))
        con.commit()
    return expected


def normalized(rows):
    return Counter(tuple(str(value) for value in row) for row in rows)


def test_all_reports_match_legacy_on_standby_with_wal_paused(
    pg, monkeypatch, tmp_path
):
    writer, reader = pg
    configure(monkeypatch, reader, writer, tmp_path)
    expected = legacy_outputs(writer)
    with writer.begin() as con:
        con.execute(
            text(
                "DELETE FROM public.__customer_total_data "
                "WHERE date > '2020-01-01'"
            )
        )
    wait_replay(writer, reader)
    with reader.connect() as con:
        con.execute(text("SELECT pg_wal_replay_pause()"))
    writes = []
    reads = []

    def record_write(con, cursor, sql, params, context, many):
        writes.append(sql)

    def record_read(con, cursor, sql, params, context, many):
        reads.append(sql)

    event.listen(writer, "before_cursor_execute", record_write)
    event.listen(reader, "before_cursor_execute", record_read)
    try:
        result = reports.run_reports()
        actual = {
            name: report
            for group in result.values()
            for name, report in group.items()
        }
        assert actual.keys() == expected.keys()
        for name, report in actual.items():
            columns, rows = expected[name]
            assert report["columns"] == columns, name
            assert normalized(report["data"]) == normalized(rows), name
            if name.startswith("customer_km_") or name == "cust_providers":
                assert report["data"] == [tuple(row) for row in rows], name
            with open(report["file"]) as file:
                csv_rows = list(csv.reader(file))
            assert csv_rows[0] == columns
            assert len(csv_rows) == len(rows) + 1
            expected_csv = [
                ["" if value is None else str(value) for value in row]
                for row in rows
            ]
            assert Counter(map(tuple, csv_rows[1:])) == Counter(
                map(tuple, expected_csv)
            ), name
        print(
            f"Parity: {len(expected)} reports, "
            f"{sum(len(rows) for _, rows in expected.values())} rows; "
            "WAL replay paused"
        )
        assert writes
        assert all(
            sql.startswith(
                (
                    "SELECT set_config",
                    "INSERT INTO public.__customer_total_data",
                )
            )
            for sql in writes
        )
        assert not any(
            sql.lstrip()
            .upper()
            .startswith(("INSERT", "CREATE", "DROP", "DO "))
            for sql in reads
        )
        with reader.connect() as con:
            assert (
                con.execute(
                    text("SELECT count(*) FROM public.__customer_total_data")
                ).scalar_one()
                == 1
            )
        with writer.connect() as con:
            assert (
                con.execute(
                    text("SELECT count(*) FROM public.__customer_total_data")
                ).scalar_one()
                > 1
            )
    finally:
        event.remove(writer, "before_cursor_execute", record_write)
        event.remove(reader, "before_cursor_execute", record_read)
        with reader.connect() as con:
            con.execute(text("SELECT pg_wal_replay_resume()"))
        wait_replay(writer, reader)


@pytest.mark.parametrize("read_kind", ["tenant", "global"])
def test_real_recovery_conflict_rolls_back_and_retry_succeeds(pg, read_kind):
    writer, reader = pg
    started = threading.Event()
    results = []
    errors = []
    attempts = []

    def before(con, cursor, sql, params, context, many):
        if "recovery_probe" in sql:
            attempts.append(sql)
            started.set()

    event.listen(reader, "before_cursor_execute", before)

    def execute():
        try:
            if read_kind == "tenant":
                result = read_schema(
                    reader,
                    "SELECT pg_sleep(3), key "
                    "FROM {schema}.reporting_awstags_values "
                    "/* recovery_probe */",
                    "org1",
                    {},
                    delay=0,
                )
            else:
                result = retry_read(
                    lambda: read_rows(
                        reader,
                        "SELECT pg_sleep(3), key "
                        "FROM org1.reporting_awstags_values "
                        "/* recovery_probe */",
                    ),
                    delay=0,
                )
            results.append(result)
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=execute)
    worker.start()
    try:
        assert started.wait(5)
        time.sleep(0.2)
        with writer.begin() as con:
            con.execute(
                text(
                    "ALTER TABLE org1.reporting_awstags_values "
                    "ADD COLUMN recovery_column integer"
                )
            )
        worker.join(12)
        assert not worker.is_alive()
        assert not errors
        assert results[0].complete and results[0].rows[0]["key"] == "x"
        assert len(attempts) == 2
    finally:
        worker.join(12)
        event.remove(reader, "before_cursor_execute", before)


def test_read_only_transaction_rejects_writes_on_primary_too(pg):
    writer, _ = pg
    with pytest.raises(DBAPIError) as caught:
        read_rows(
            writer, "DELETE FROM org1.reporting_awstags_values RETURNING key"
        )
    assert caught.value.orig.pgcode == "25006"


def test_writer_lock_timeout_and_atomic_totals_rollback(pg):
    writer, reader = pg
    with writer.connect() as blocker:
        transaction = blocker.begin()
        blocker.execute(
            text("LOCK public.__customer_total_data IN ACCESS EXCLUSIVE MODE")
        )
        try:
            with pytest.raises(DBAPIError) as caught:
                write_totals(
                    writer,
                    "INSERT INTO public.__customer_total_data (date) "
                    "VALUES (:date)",
                    [{"date": "2026-02-01"}],
                    lock_timeout=50,
                )
            assert caught.value.orig.pgcode == "55P03"
        finally:
            transaction.rollback()
    with writer.connect() as con:
        assert (
            con.execute(
                text("SELECT count(*) FROM public.__customer_total_data")
            ).scalar_one()
            == 1
        )


def test_typed_intermediate_conversion_matches_postgres_insert(pg):
    writer, reader = pg
    with writer.begin() as con:
        sql = legacy_sql("cust_node_report_setup.sql")
        con.execute(text(sql))
        con.execute(
            text(
                "INSERT INTO __cust_node_report "
                "(cpu_cores, memory_gigabytes) VALUES (1.6, 4.4)"
            )
        )
        legacy = con.execute(
            text("SELECT cpu_cores, memory_gigabytes FROM __cust_node_report")
        ).one()
    result = read_schema(
        reader,
        reports._required_sql("sql/cust_node_report_setup_schema.sql"),
        "org1",
        {"customer": "org1", **reports.USAGE_REPORT_PARAMS},
    )
    assert (
        result.rows[0]["cpu_cores"],
        result.rows[0]["memory_gigabytes"],
    ) == tuple(legacy)


@pytest.mark.parametrize(
    "failed_table,weekly,totals_should_commit",
    [
        ("reporting_ocptags_values", False, True),
        ("cost_model", True, True),
        ("reporting_ocpusagelineitem_daily_summary", True, True),
        ("reporting_aws_cost_summary_p", False, False),
        ("reporting_ocp_cost_summary_p", False, False),
        ("reporting_ocp_pod_summary_by_node_p", False, False),
    ],
)
def test_incomplete_inputs_block_delivery_and_scope_totals_write(
    pg,
    monkeypatch,
    tmp_path,
    caplog,
    failed_table,
    weekly,
    totals_should_commit,
):
    import logging
    import runpy
    from unittest.mock import Mock

    import prometheus_client
    from kokudaily import send
    from test_replica import conflict

    writer, reader = pg
    configure(monkeypatch, reader, writer, tmp_path)
    if not weekly:
        monkeypatch.setattr(
            reports.Config, "WEEKLY_REPORT_SCHEDULED_DAY", None
        )
    monkeypatch.setattr(reports.Config, "REPLICA_RETRY_DELAY", 0)
    monkeypatch.setattr(reports.Config, "EMAIL_GROUPS", {})
    monkeypatch.setattr(reports.Config, "PROMETHEUS_PUSH_GATEWAY", "unused")
    monkeypatch.setattr(
        logging.getLogger(), "handlers", list(logging.getLogger().handlers)
    )
    monkeypatch.setattr(
        logging.getLogger(), "level", logging.getLogger().level
    )
    deliveries = [Mock() for _ in range(5)]
    for name, delivery in zip(
        ("email", "s3", "prometheus", "create_zip_archive"), deliveries
    ):
        monkeypatch.setattr(send, name, delivery)
    monkeypatch.setattr(prometheus_client, "push_to_gateway", deliveries[-1])
    save_report = Mock(wraps=reports._save_report)
    merge_history = Mock(wraps=reports.merge_history)
    monkeypatch.setattr(reports, "_save_report", save_report)
    monkeypatch.setattr(reports, "merge_history", merge_history)
    attempts = []
    reads = []
    writes = []
    with writer.connect() as con:
        original_totals = con.execute(
            text("SELECT * FROM public.__customer_total_data ORDER BY date")
        ).all()

    def fail_schema(con, cursor, sql, params, context, many):
        reads.append(sql)
        # cost_model is also read by daily OCP costs; fail only its weekly
        # extraction query so the key-metrics inputs remain independent.
        targeted_query = failed_table != "cost_model" or sql.startswith(
            "WITH schema_rows (customer, cost_model_id"
        )
        if targeted_query and "org1." + failed_table in sql:
            attempts.append(sql)
            raise conflict()

    def record_write(con, cursor, sql, params, context, many):
        writes.append(sql)

    event.listen(reader, "before_cursor_execute", fail_schema)
    event.listen(writer, "before_cursor_execute", record_write)
    try:
        with pytest.raises(reports.IncompleteReportInputs, match="incomplete"):
            runpy.run_path("job.py", run_name="__main__")
        assert len(attempts) == 3
        assert any("org2." + failed_table in sql for sql in reads)
        for delivery in deliveries:
            delivery.assert_not_called()
        save_report.assert_not_called()
        merge_history.assert_not_called()
        assert (
            any(sql.startswith("INSERT") for sql in writes)
            == totals_should_commit
        )
        with writer.connect() as con:
            final_totals = con.execute(
                text(
                    "SELECT * FROM public.__customer_total_data ORDER BY date"
                )
            ).all()
        if totals_should_commit:
            assert len(final_totals) > len(original_totals)
        else:
            assert final_totals == original_totals
            assert "suppressing daily totals" in caplog.text
    finally:
        event.remove(reader, "before_cursor_execute", fail_schema)
        event.remove(writer, "before_cursor_execute", record_write)


def test_upserts_preserve_history_and_enforce_timeout(
    pg,
):
    writer, _ = pg
    sql = reports._required_sql("sql/key_metrics/cust_total_data_upsert.sql")
    with writer.connect() as con:
        columns = list(
            con.execute(
                text("SELECT * FROM public.__customer_total_data LIMIT 0")
            ).keys()
        )
    row = dict.fromkeys(columns)
    row.update(date="2026-02-01", total_aws_unblended_cost="12.34")
    for _ in range(2):
        write_totals(writer, sql, [row])
    with writer.connect() as con:
        assert (
            con.execute(
                text("SELECT count(*) FROM public.__customer_total_data")
            ).scalar_one()
            == 2
        )
        assert (
            str(
                con.execute(
                    text(
                        "SELECT total_aws_unblended_cost "
                        "FROM public.__customer_total_data "
                        "WHERE date='2026-02-01'"
                    )
                ).scalar_one()
            )
            == "12.34"
        )
    with pytest.raises(DBAPIError) as caught:
        write_totals(
            writer, "SELECT pg_sleep(1)", [{"unused": 1}], statement_timeout=50
        )
    assert caught.value.orig.pgcode == "57014"
    assert not is_recovery_conflict(caught.value)


def test_failure_after_first_100_dates_leaves_all_totals_unchanged(pg):
    writer, _ = pg
    rows = [
        {"date": date(2024, 1, 1) + timedelta(days=day)} for day in range(200)
    ]
    rows.append({"date": "not-a-date"})
    with pytest.raises(DBAPIError):
        write_totals(
            writer,
            "INSERT INTO public.__customer_total_data (date) VALUES (:date)",
            rows,
        )
    with writer.connect() as con:
        assert (
            con.execute(
                text("SELECT count(*) FROM public.__customer_total_data")
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize(
    "json_value",
    [
        None,
        "null",
        "{}",
        "[]",
        '{"tag_rates":null,"value":123456789.1234567891}',
        '[{"tag_rates":{"value":"1.25"}}]',
        '"null"',
    ],
)
def test_cost_model_json_roundtrip_matches_legacy(pg, json_value):
    writer, reader = pg
    setup = "cust_cost_model_report_setup_schema.sql"
    probe = (
        "SELECT rates IS NULL AS rates_sql_null, "
        "markup IS NULL AS markup_sql_null, "
        "rates::text AS rates_json, markup::text AS markup_json "
        "FROM __cust_cost_model_report ORDER BY cost_model_id"
    )
    count_sql = reports._required_sql("sql/cust_cost_model_report_counts.sql")
    with writer.begin() as con:
        con.execute(
            text(
                "UPDATE org1.cost_model SET source_type='AWS', "
                "rates=CAST(:value AS jsonb), markup=CAST(:value AS jsonb)"
            ),
            {"value": json_value},
        )
        con.execute(text(legacy_sql("cust_cost_model_report_setup.sql")))
        con.execute(
            text(render_schema_sql(legacy_sql(setup), "org1")),
            {"customer": "org1"},
        )
        expected_values = [
            dict(row) for row in con.execute(text(probe)).mappings()
        ]
        expected_counts = [
            dict(row) for row in con.execute(text(count_sql)).mappings()
        ]
    wait_replay(writer, reader)
    rows = read_schema(
        reader,
        reports._required_sql("sql/" + setup),
        "org1",
        {"customer": "org1"},
    ).rows
    datasets = {"__cust_cost_model_report": rows}
    for sql, expected in (
        (probe, expected_values),
        (count_sql, expected_counts),
    ):
        bound_sql, params = reports.bind_datasets(
            sql, datasets, reports.DEFINITIONS
        )
        assert read_rows(reader, bound_sql, params).rows == expected
