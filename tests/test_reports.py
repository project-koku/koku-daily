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
