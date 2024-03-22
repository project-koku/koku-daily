"""Configuration loader for application."""
import json
import logging
import os

from prometheus_client import CollectorRegistry

LOG = logging.getLogger(__name__)
REGISTRY = CollectorRegistry()


# pylint: disable=too-few-public-methods,simplifiable-if-expression
class Config:
    """Configuration for app."""

    CLOWDER_ENABLED = os.getenv("CLOWDER_ENABLED", "false")
    if CLOWDER_ENABLED.lower() == "true":
        from app_common_python import LoadedConfig

        # Database
        DB_ENGINE = os.getenv("DATABASE_ENGINE", "postgresql")
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
        DB_ENGINE = os.getenv("DATABASE_ENGINE", "postgresql")
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

    SQLALCHEMY_DATABASE_URI = (
        f"{DB_ENGINE}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_POOL_SIZE = 10

    NAMESPACE = os.getenv("NAMESPACE")

    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    EMAIL_GROUPS = os.getenv("EMAIL_GROUPS")
    if EMAIL_GROUPS:
        try:
            EMAIL_GROUPS = json.loads(EMAIL_GROUPS)
        except:  # noqa: E722
            LOG.error("Invalid EMAIL_GROUPS input. Not JSON.")
            EMAIL_GROUPS = {}

    PROMETHEUS_PUSH_GATEWAY = os.getenv("PROMETHEUS_PUSH_GATEWAY")

    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = os.getenv("APP_PORT", "8080")

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

    WEEKLY_REPORT_SCHEDULED_DAY = os.getenv("WEEKLY_REPORT_SCHEDULED_DAY")
    if WEEKLY_REPORT_SCHEDULED_DAY:
        try:
            WEEKLY_REPORT_SCHEDULED_DAY = int(WEEKLY_REPORT_SCHEDULED_DAY)
        except ValueError:
            LOG.error(
                "Invalid WEEKLY_REPORT_SCHEDULED_DAY input."
                " Must be integer 0-6."
            )
            WEEKLY_REPORT_SCHEDULED_DAY = None
    RUN_DAILY_REPORTS = os.getenv("RUN_DAILY_REPORTS", "")
    if RUN_DAILY_REPORTS.lower() == "true":
        RUN_DAILY_REPORTS = True
    else:
        RUN_DAILY_REPORTS = False

    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
