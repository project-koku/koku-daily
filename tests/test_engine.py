"""Configuration must never send report work to the writer by fallback."""

from unittest.mock import Mock

import pytest
from kokudaily import engine
from sqlalchemy.engine import make_url


def test_ro_endpoint_is_required_before_engine_creation(monkeypatch):
    monkeypatch.setattr(engine.Config, "RO_DB_HOST", "", raising=False)
    factory = Mock()
    monkeypatch.setattr(engine.sqlalchemy, "create_engine", factory)
    with pytest.raises(ValueError, match="DATABASE_RO_HOST"):
        engine.create_engine(readonly=True)
    factory.assert_not_called()


def test_separate_ro_url_preserves_special_password_characters(monkeypatch):
    for key, value in {
        "RO_DB_HOST": "replica",
        "RO_DB_PORT": 5433,
        "RO_DB_USER": "reader",
        "RO_DB_PASSWORD": "p@ss:/#",
        "RO_DB_NAME": "reports",
    }.items():
        monkeypatch.setattr(engine.Config, key, value, raising=False)
    factory = Mock()
    monkeypatch.setattr(engine.sqlalchemy, "create_engine", factory)
    engine.create_engine(readonly=True)
    url = make_url(factory.call_args.args[0])
    assert (url.host, url.port, url.username, url.password, url.database) == (
        "replica",
        5433,
        "reader",
        "p@ss:/#",
        "reports",
    )
    assert factory.call_args.kwargs["hide_parameters"] is True


def test_tls_options_apply_to_both_engines(monkeypatch):
    certificate_path = "/etc/ssl/certs/server.pem"
    real_exists = engine.os.path.exists
    real_isfile = engine.os.path.isfile
    real_stat = engine.os.stat
    monkeypatch.setattr(
        engine.os.path,
        "exists",
        lambda path: True if path == certificate_path else real_exists(path),
    )
    monkeypatch.setattr(
        engine.os.path,
        "isfile",
        lambda path: True if path == certificate_path else real_isfile(path),
    )
    monkeypatch.setattr(
        engine.os,
        "stat",
        lambda path, *args, **kwargs: (
            Mock(st_size=12)
            if path == certificate_path
            else real_stat(path, *args, **kwargs)
        ),
    )
    kwargs, certificate = engine._create_engine_kwargs()
    assert kwargs["connect_args"] == {
        "sslmode": "verify-full",
        "sslrootcert": certificate,
    }
