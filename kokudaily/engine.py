"""SQLAlchemy database engine creation."""
import os

import sqlalchemy
from kokudaily.config import Config

CLOWDER_ENABLED = os.getenv("CLOWDER_ENABLED", "false")
if CLOWDER_ENABLED.lower() == "true":
    from app_common_python import LoadedConfig, SmartAppConfig  # noqa


def _create_engine_kwargs():
    """Create the kwargs for the database engine.

    Returns:
        (Dict): "Engine arguments"
        (String): "Certificate file path"
    """
    kwargs = {
        "client_encoding": "utf8",
        "pool_size": Config.SQLALCHEMY_POOL_SIZE,
    }

    cert_file = "/etc/ssl/certs/server.pem"
    if CLOWDER_ENABLED.lower() == "true":
        cert_file = LoadedConfig.rds_ca()

    if (
        os.path.exists(cert_file)
        and os.path.isfile(cert_file)
        and os.stat(cert_file).st_size > 0
    ):
        kwargs["connect_args"] = {
            "sslmode": "verify-full",
            "sslrootcert": cert_file,
        }
    return kwargs, cert_file


def create_engine(uri=Config.SQLALCHEMY_DATABASE_URI, add_kwargs=True):
    """Create a database engine to manage DB connections.

    Args:
        None
    Returns:
        (sqlalchemy.engine.base.Engine): "SQLAlchemy engine object",
        (sqlalchemy.sql.schema.MetaData): "SQLAlchemy engine metadata"
    """
    kwargs = {}
    if add_kwargs:
        kwargs, _ = _create_engine_kwargs()
    return sqlalchemy.create_engine(uri, **kwargs)


DB_ENGINE = create_engine()
REDSHIFT_ENGINE = None
if Config.REDSHIFT_DATABASE_URI:
    REDSHIFT_ENGINE = create_engine(
        uri=Config.REDSHIFT_DATABASE_URI, add_kwargs=False
    )
