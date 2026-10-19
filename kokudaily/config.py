"""Configuration loader for application."""

import json
import logging
import math
import os

from prometheus_client import CollectorRegistry
from sqlalchemy.engine import URL

LOG = logging.getLogger(__name__)
REGISTRY = CollectorRegistry()


def positive_setting(name, default):
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


# pylint: disable=too-few-public-methods,simplifiable-if-expression
class Config:
    """Configuration for app."""

    CLOWDER_ENABLED = os.getenv("CLOWDER_ENABLED", "false")
    if CLOWDER_ENABLED.lower() == "true":
        from app_common_python import LoadedConfig

        # Database
        DB_ENGINE = os.getenv("DATABASE_ENGINE", "postgresql+psycopg2")
        DB_NAME = LoadedConfig.database.name
        DB_USER = LoadedConfig.database.username
        DB_PASSWORD = LoadedConfig.database.password
        DB_HOST = LoadedConfig.database.hostname
        DB_PORT = LoadedConfig.database.port

        MINIO_ENDPOINT = LoadedConfig.objectStore.hostname
        MINIO_ENDPOINT_PORT = LoadedConfig.objectStore.port
        MINIO_SECURE = bool(LoadedConfig.objectStore.tls)

        if LoadedConfig.objectStore.accessKey:
            MINIO_ACCESS_KEY = LoadedConfig.objectStore.accessKey
        else:
            MINIO_ACCESS_KEY = LoadedConfig.objectStore.buckets[0].accessKey

        if LoadedConfig.objectStore.secretKey:
            MINIO_SECRET_KEY = LoadedConfig.objectStore.secretKey
        else:
            MINIO_SECRET_KEY = LoadedConfig.objectStore.buckets[0].secretKey

        MINIO_BUCKET = LoadedConfig.objectStore.buckets[0].name
    else:
        # Database
        DB_ENGINE = os.getenv("DATABASE_ENGINE", "postgresql+psycopg2")
        DB_NAME = os.getenv("DATABASE_NAME", "postgres")
        DB_USER = os.getenv("DATABASE_USER", "postgres")
        DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "postgres")
        DB_HOST = os.getenv("DATABASE_HOST", "localhost")
        DB_PORT = os.getenv("DATABASE_PORT", "15432")
        MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", None)
        MINIO_ENDPOINT_PORT = os.getenv("MINIO_ENDPOINT_PORT", 443)
        MINIO_SECURE = bool(os.getenv("MINIO_SECURE", True))
        MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", None)
        MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", None)
        MINIO_BUCKET = os.getenv("MINIO_BUCKET", None)

    # The driver is explicit: SQLAlchemy 2.1 maps a bare "postgresql://" URL to
    # psycopg (v3), but the image only installs psycopg2.
    SQLALCHEMY_DATABASE_URI = URL.create(
        DB_ENGINE,
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
    )

    # app-common-python's database config exposes the primary only. Never
    # derive a replica hostname or silently send expensive reads to primary.
    RO_DB_HOST = os.getenv("DATABASE_RO_HOST", "")
    RO_DB_PORT = positive_setting("DATABASE_RO_PORT", DB_PORT)
    RO_DB_NAME = os.getenv("DATABASE_RO_NAME", DB_NAME)
    RO_DB_USER = os.getenv("DATABASE_RO_USER", DB_USER)
    RO_DB_PASSWORD = os.getenv("DATABASE_RO_PASSWORD", DB_PASSWORD)
    REPLICA_RETRY_ATTEMPTS = positive_setting("REPLICA_RETRY_ATTEMPTS", 3)
    REPLICA_RETRY_DELAY = float(os.getenv("REPLICA_RETRY_DELAY", "1"))
    if REPLICA_RETRY_DELAY < 0 or not math.isfinite(REPLICA_RETRY_DELAY):
        raise ValueError("REPLICA_RETRY_DELAY must be finite and nonnegative")
    REPORT_STATEMENT_TIMEOUT_MS = positive_setting(
        "REPORT_STATEMENT_TIMEOUT_MS", 5000
    )
    REPORT_LOCK_TIMEOUT_MS = positive_setting("REPORT_LOCK_TIMEOUT_MS", 1000)

    REPORT_STAGING_DIR = os.getenv("REPORT_STAGING_DIR") or None
    if REPORT_STAGING_DIR:
        os.environ["TMPDIR"] = REPORT_STAGING_DIR
        os.environ["SQLITE_TMPDIR"] = REPORT_STAGING_DIR

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_POOL_SIZE = 10

    NAMESPACE = os.getenv("NAMESPACE")

    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    EMAIL_GROUPS: str | dict | None = os.getenv("EMAIL_GROUPS")
    if isinstance(EMAIL_GROUPS, str) and EMAIL_GROUPS:
        try:
            EMAIL_GROUPS = json.loads(EMAIL_GROUPS)
        except:  # noqa: E722
            LOG.error("Invalid EMAIL_GROUPS input. Not JSON.")
            EMAIL_GROUPS = {}

    PROMETHEUS_PUSH_GATEWAY = os.getenv("PROMETHEUS_PUSH_GATEWAY")

    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: str | int = os.getenv("APP_PORT", "8080")

    if APP_HOST != "127.0.0.1":
        LOG.info(
            "Listening on %s:%s. This might be insecure.", APP_HOST, APP_PORT
        )

    try:
        APP_PORT = int(APP_PORT)
    except ValueError:
        LOG.info("Defined APP_PORT was not an integer; defaulting to 8080.")
        APP_PORT = 8080

    APP_URL_PREFIX = os.getenv("APP_URL_PREFIX", "")

    # S3 configuration
    WAREHOUSE_PATH = os.getenv("WAREHOUSE_PATH", "metrics")

    WEEKLY_REPORT_SCHEDULED_DAY: str | int | None = os.getenv(
        "WEEKLY_REPORT_SCHEDULED_DAY"
    )
    if WEEKLY_REPORT_SCHEDULED_DAY:
        try:
            WEEKLY_REPORT_SCHEDULED_DAY = int(WEEKLY_REPORT_SCHEDULED_DAY)
        except ValueError:
            LOG.error(
                "Invalid WEEKLY_REPORT_SCHEDULED_DAY input."
                " Must be integer 0-6."
            )
            WEEKLY_REPORT_SCHEDULED_DAY = None
    RUN_DAILY_REPORTS: str | bool = os.getenv("RUN_DAILY_REPORTS", "")
    if (
        isinstance(RUN_DAILY_REPORTS, str)
        and RUN_DAILY_REPORTS.lower() == "true"
    ):
        RUN_DAILY_REPORTS = True
    else:
        RUN_DAILY_REPORTS = False

    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()

    KEY_METRICS_NUM_MONTHS = int(os.getenv("KEY_METRICS_NUM_MONTHS", 2))
