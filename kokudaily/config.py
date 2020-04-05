"""Configuration loader for application."""
import json
import logging
import os


LOG = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods,simplifiable-if-expression
class Config:
    """Configuration for app."""

    # Database
    DB_ENGINE = os.getenv("DATABASE_ENGINE", "postgresql")
    DB_NAME = os.getenv("DATABASE_NAME", "postgres")
    DB_USER = os.getenv("DATABASE_USER", "postgres")
    DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "postgres")
    DB_HOST = os.getenv("DATABASE_HOST", "localhost")
    DB_PORT = os.getenv("DATABASE_PORT", "15432")

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
