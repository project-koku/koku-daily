"""Full orchestration must use RO even for ordinary reports."""

from unittest.mock import Mock

from kokudaily import reports
from test_replica import Engine


def test_read_only_run_never_connects_writer_and_repeats(
    monkeypatch, tmp_path
):
    writer = Mock()
    writer.connect.side_effect = AssertionError(
        "writer used for a report read"
    )
    reader = Engine([[{"count": 2}], [{"count": 2}]])
    reader.dispose = Mock()
    factory = Mock(return_value=reader)
    monkeypatch.setattr(reports, "DB_ENGINE", writer)
    monkeypatch.setattr(reports, "create_engine", factory, raising=False)
    monkeypatch.setattr(reports, "REQUIRES", [])
    monkeypatch.setattr(
        reports,
        "REPORTS",
        {
            "test": {
                "file": "sql/count_filtered_users.sql",
                "target": "engineering",
            }
        },
    )
    monkeypatch.setattr(reports.Config, "NAMESPACE", "hccm-prod")
    monkeypatch.setattr(reports.Config, "RUN_DAILY_REPORTS", False)
    monkeypatch.setattr(reports.Config, "WEEKLY_REPORT_SCHEDULED_DAY", None)
    monkeypatch.setattr(reports, "gettempdir", lambda: str(tmp_path))
    for _ in range(2):
        result = reports.run_reports()
        assert result["engineering"]["test"]["data_dicts"] == [{"count": 2}]
        assert result["engineering"]["test"]["data"] == [(2,)]
    writer.connect.assert_not_called()
    writer.begin.assert_not_called()
    assert reader.events.count("commit") == 2
    assert set(reports.REPORTS) == {"test"}


def test_missing_sql_is_a_clear_failure():
    import pytest

    with pytest.raises(FileNotFoundError, match="Missing report SQL"):
        reports._required_sql("sql/does-not-exist.sql")


def test_filters_skip_reports_without_database_queries(monkeypatch):
    reader = Engine()
    reader.dispose = Mock()
    monkeypatch.setattr(reports, "create_engine", lambda readonly: reader)
    monkeypatch.setattr(reports, "REQUIRES", [])
    monkeypatch.setattr(reports.Config, "RUN_DAILY_REPORTS", False)
    monkeypatch.setattr(reports.Config, "WEEKLY_REPORT_SCHEDULED_DAY", None)
    monkeypatch.setattr(reports.Config, "NAMESPACE", "dev")
    monkeypatch.setattr(
        reports,
        "REPORTS",
        {
            "wrong_namespace": {"namespace": "prod"},
            "wrong_target": {"target": "engineering"},
        },
    )
    assert reports.run_reports(filter_target="marketing") == {}
    assert reader.events == []


def test_disabled_daily_and_weekly_tasks_do_no_setup(monkeypatch):
    reader = Engine()
    reader.dispose = Mock()
    monkeypatch.setattr(reports, "create_engine", lambda readonly: reader)
    monkeypatch.setattr(reports.Config, "RUN_DAILY_REPORTS", False)
    monkeypatch.setattr(reports.Config, "WEEKLY_REPORT_SCHEDULED_DAY", None)
    monkeypatch.setattr(reports, "REPORTS", {})
    assert reports.run_reports() == {}
    assert reader.events == []


def test_active_setup_captures_one_cutoff_for_all_tenants_and_reports(
    monkeypatch,
):
    from datetime import datetime, timezone

    cutoff = datetime(2026, 1, 31, 23, 59, tzinfo=timezone.utc)
    tag_row = {
        "customer": "org1",
        "openshift_label_key_count": 1,
        "aws_tag_key_count": 0,
        "azure_tag_key_count": 0,
        "gcp_label_key_count": 0,
    }
    node_row = {
        "customer": "org1",
        "provider_id": "provider1",
        "cluster_id": "cluster1",
        "node": "node1",
        "report_month": cutoff.date(),
        "cpu_cores": 4,
        "memory_gigabytes": 16,
    }
    reader = Engine(
        [
            [{"cutoff": cutoff}],
            [{"schema_name": "org1"}, {"schema_name": "org2"}],
            [{"exists": 1}],
            [tag_row],
            [{"exists": 1}],
            [dict(tag_row, customer="org2")],
            [{"schema_name": "org1"}],
            [{"exists": 1}],
            [node_row],
        ]
    )
    monkeypatch.setattr(reports.Config, "RUN_DAILY_REPORTS", True)
    monkeypatch.setattr(
        reports,
        "REQUIRES",
        [
            {
                "setup": [
                    {
                        "frequency": "daily",
                        "per_schema_file": (
                            "sql/" "cust_tag_report_setup_schema.sql"
                        ),
                    },
                    {
                        "frequency": "weekly",
                        "per_schema_file": (
                            "sql/" "cust_node_report_setup_schema.sql"
                        ),
                    },
                ]
            }
        ],
    )
    datasets = reports._collect_datasets(reader, run_weeklys=True)
    assert len(datasets["__cust_tag_report"]) == 2
    assert datasets["__cust_node_report"] == [node_row]
    calls = [event for event in reader.events if isinstance(event, tuple)]
    assert sum("clock_timestamp()" in sql for sql, _ in calls) == 1
    assert [
        params["run_cutoff"]
        for _, params in calls
        if params and "customer" in params
    ] == [cutoff] * 3
    assert reader.events.count("commit") == 6
    assert not reader.active


def test_recovery_conflicts_retry_at_every_global_read(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from kokudaily import replica
    from test_replica import conflict

    cutoff = datetime(2026, 1, 31, tzinfo=timezone.utc)
    reader = Engine(
        [
            conflict(),
            [{"cutoff": cutoff}],
            conflict(),
            [{"schema_name": "org1"}],
            [{"exists": 1}],
            [],
            conflict(),
            [{"date": cutoff.date()}],
            conflict(),
            [],
            conflict(),
            [{"count": 2}],
        ]
    )
    reader.dispose = Mock()
    writer = Engine([[]])
    sleep = Mock()
    monkeypatch.setattr(replica.time, "sleep", sleep)
    monkeypatch.setattr(reports.Config, "REPLICA_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(reports.Config, "REPLICA_RETRY_DELAY", 0.25)
    monkeypatch.setattr(reports.Config, "RUN_DAILY_REPORTS", True)
    monkeypatch.setattr(reports.Config, "WEEKLY_REPORT_SCHEDULED_DAY", None)
    monkeypatch.setattr(reports.Config, "NAMESPACE", "test")
    monkeypatch.setattr(reports, "create_engine", lambda readonly: reader)
    monkeypatch.setattr(reports, "DB_ENGINE", writer)
    monkeypatch.setattr(reports, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(reports, "DAILY_REPORTS", {})
    monkeypatch.setattr(
        reports,
        "REPORTS",
        {
            "test": {"file": "sql/count_filtered_users.sql", "target": "test"},
        },
    )
    monkeypatch.setattr(
        reports,
        "REQUIRES",
        [
            {
                "setup": [
                    {
                        "frequency": "daily",
                        "per_schema_file": "sql/cust_tag_report_setup_schema.sql",
                    },
                    {
                        "frequency": "daily",
                        "file": "sql/key_metrics/cust_total_data_setup.sql",
                    },
                ]
            }
        ],
    )
    result = reports.run_reports()
    assert result["test"]["test"]["data"] == [(2,)]
    assert reader.events.count("rollback") == 5
    assert reader.events.count("close") == 11
    assert writer.events.count("commit") == 1
    assert sleep.call_args_list == [((0.25,),)] * 5
    reader.dispose.assert_called_once_with()
