"""Load real configuration with environment and Clowder-shaped inputs."""

import importlib
import sys
from types import SimpleNamespace

import pytest
from kokudaily import config


@pytest.fixture(autouse=True)
def restore_config(monkeypatch):
    yield
    monkeypatch.undo()
    importlib.reload(config)


def test_ro_environment_inherits_only_credentials_not_host(monkeypatch):
    monkeypatch.setenv("DATABASE_PASSWORD", "secret@test")
    monkeypatch.setenv("DATABASE_HOST", "writer")
    monkeypatch.delenv("DATABASE_RO_HOST", raising=False)
    cfg = importlib.reload(config).Config
    assert not cfg.RO_DB_HOST
    assert cfg.RO_DB_PASSWORD == "secret@test"
    monkeypatch.setenv("DATABASE_RO_HOST", "replica")
    monkeypatch.setenv("DATABASE_RO_USER", "reader")
    cfg = importlib.reload(config).Config
    assert cfg.RO_DB_HOST == "replica" and cfg.RO_DB_USER == "reader"


def test_clowder_writer_and_explicit_reader(monkeypatch):
    database = SimpleNamespace(
        name="koku",
        username="app",
        password="test",
        hostname="clowder-writer",
        port=5432,
    )
    store = SimpleNamespace(
        hostname="s3",
        port=443,
        tls=True,
        accessKey="test",
        secretKey="test",
        buckets=[SimpleNamespace(name="test")],
    )
    monkeypatch.setitem(
        sys.modules,
        "app_common_python",
        SimpleNamespace(
            LoadedConfig=SimpleNamespace(database=database, objectStore=store)
        ),
    )
    monkeypatch.setenv("CLOWDER_ENABLED", "true")
    monkeypatch.setenv("DATABASE_RO_HOST", "replica")
    cfg = importlib.reload(config).Config
    assert cfg.DB_HOST == "clowder-writer"
    assert cfg.RO_DB_HOST == "replica"
    assert cfg.RO_DB_USER == "app" and cfg.RO_DB_PASSWORD == "test"


@pytest.mark.parametrize(
    "name,value",
    [
        ("REPORT_LOCK_TIMEOUT_MS", "-1"),
        ("REPORT_STATEMENT_TIMEOUT_MS", "oops"),
        ("REPLICA_RETRY_ATTEMPTS", "0"),
        ("REPLICA_RETRY_DELAY", "nan"),
    ],
)
def test_invalid_operational_settings_fail_configuration(
    monkeypatch, name, value
):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        importlib.reload(config)


def test_invalid_email_groups_preserves_existing_logged_fallback(
    monkeypatch, caplog
):
    monkeypatch.setenv("EMAIL_GROUPS", "invalid-json")
    assert importlib.reload(config).Config.EMAIL_GROUPS == {}
    assert "Invalid EMAIL_GROUPS" in caplog.text


def test_deployment_wires_ro_and_writer_limits_to_both_jobs():
    from pathlib import Path
    import yaml

    template = yaml.safe_load(Path("deploy/clowdapp.yaml").read_text())
    app = next(obj for obj in template["objects"] if obj["kind"] == "ClowdApp")
    assert app["spec"]["database"]["sharedDbAppName"] == "koku"
    for job in app["spec"]["jobs"]:
        env = {entry["name"]: entry for entry in job["podSpec"]["env"]}
        for variable, key in (
            ("DATABASE_RO_HOST", "db.host"),
            ("DATABASE_RO_PORT", "db.port"),
        ):
            assert env[variable]["valueFrom"]["secretKeyRef"] == {
                "name": "${KOKU_READ_ONLY_DB}",
                "key": key,
            }
        assert "REPORT_WRITE_BATCH_SIZE" not in env
        assert "DATABASE_RO_USER" not in env
        assert "DATABASE_RO_PASSWORD" not in env
        for setting in (
            "REPORT_STATEMENT_TIMEOUT_MS",
            "REPORT_LOCK_TIMEOUT_MS",
            "REPLICA_RETRY_ATTEMPTS",
            "REPLICA_RETRY_DELAY",
        ):
            assert env[setting]["value"] == "${" + setting + "}"
    parameter = next(
        p for p in template["parameters"] if p["name"] == "KOKU_READ_ONLY_DB"
    )
    assert parameter["required"] is True
    assert parameter["value"] == "koku-db-ro"


def test_touched_schedule_types_preserve_normalization_and_port_fallback(
    monkeypatch, caplog
):
    monkeypatch.setenv("WEEKLY_REPORT_SCHEDULED_DAY", "6")
    monkeypatch.setenv("RUN_DAILY_REPORTS", "true")
    monkeypatch.setenv("APP_PORT", "invalid")
    cfg = importlib.reload(config).Config
    assert cfg.WEEKLY_REPORT_SCHEDULED_DAY == 6
    assert cfg.RUN_DAILY_REPORTS is True
    assert cfg.APP_PORT == 8080
