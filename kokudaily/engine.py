"""SQLAlchemy database engine creation."""
import os

import sqlalchemy
from kokudaily.config import Config


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


def create_engine():
    """Create a database engine to manage DB connections.

    Args:
        None
    Returns:
        (sqlalchemy.engine.base.Engine): "SQLAlchemy engine object",
        (sqlalchemy.sql.schema.MetaData): "SQLAlchemy engine metadata"
    """
    kwargs, _ = _create_engine_kwargs()
    return sqlalchemy.create_engine(Config.SQLALCHEMY_DATABASE_URI, **kwargs)


DB_ENGINE = create_engine()
