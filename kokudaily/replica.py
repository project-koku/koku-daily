"""Short read-only transactions and bounded final writes for reporting."""

import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import TypeVar

from kokudaily.setup_runner import render_schema_sql
from kokudaily.setup_runner import validate_schema_name
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

LOG = logging.getLogger(__name__)
Rows = list[dict[str, Any]]
ReadResult = TypeVar("ReadResult")


@dataclass
class ReportRows:
    columns: list[str]
    rows: Rows
    complete: bool = True


def read_rows(
    engine: Any,
    sql: str,
    params: dict | None = None,
    schema: str | None = None,
) -> ReportRows:
    """Consume rows before ending the transaction and returning to the pool."""
    with engine.connect() as con:
        with con.begin():
            con.execute(text("SET TRANSACTION READ ONLY"))
            if schema is not None:
                exists = con.execute(
                    text("SELECT 1 FROM pg_namespace WHERE nspname = :schema"),
                    {"schema": schema},
                )
                if not list(exists.mappings()):
                    LOG.warning("Schema %s disappeared; skipping.", schema)
                    return ReportRows([], [])
            result = con.execute(text(sql), params or {})
            return ReportRows(
                list(result.keys()), [dict(row) for row in result.mappings()]
            )


def is_recovery_conflict(error: DBAPIError) -> bool:
    """Distinguish recovery conflicts from user cancellations."""
    original = error.orig
    code = getattr(original, "pgcode", None)
    diagnostic = getattr(original, "diag", None)
    message = getattr(diagnostic, "message_primary", "") or ""
    return code in {"40001", "57014", "57P01"} and (
        "conflict with recovery" in message.lower()
    )


def retry_read(
    operation: Callable[[], ReadResult],
    attempts: int = 3,
    delay: float = 1,
) -> ReadResult:
    """Retry a complete RO transaction; fail when recovery retries exhaust."""
    if attempts < 1 or delay < 0 or not math.isfinite(delay):
        raise ValueError("Invalid replica retry settings")
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except DBAPIError as error:
            if not is_recovery_conflict(error):
                raise
            LOG.warning(
                "Recovery conflict on replica read, attempt %s/%s",
                attempt,
                attempts,
            )
            if attempt == attempts:
                raise
            time.sleep(delay)
    raise AssertionError("Unreachable replica retry state")


def read_schema(
    engine: Any,
    sql: str,
    schema: str,
    params: dict,
    attempts: int = 3,
    delay: float = 1,
    check_exists: bool = False,
) -> ReportRows:
    schema = validate_schema_name(schema)
    if attempts < 1 or delay < 0 or not math.isfinite(delay):
        raise ValueError("Invalid replica retry settings")
    rendered = render_schema_sql(sql, schema)
    for attempt in range(1, attempts + 1):
        try:
            return read_rows(
                engine, rendered, params, schema if check_exists else None
            )
        except DBAPIError as error:
            if not is_recovery_conflict(error):
                raise
            LOG.warning(
                "Recovery conflict for %s, attempt %s/%s",
                schema,
                attempt,
                attempts,
            )
            if attempt < attempts:
                time.sleep(delay)
    LOG.error(
        "Report inputs incomplete: exhausted recovery retries for %s", schema
    )
    return ReportRows([], [], complete=False)


def write_totals(
    engine: Any,
    sql: str,
    rows: Rows,
    statement_timeout: int = 5000,
    lock_timeout: int = 1000,
) -> None:
    if min(statement_timeout, lock_timeout) < 1:
        raise ValueError("Writer timeouts must be positive")
    if not rows:
        return
    with engine.begin() as con:
        for setting, value in (
            ("statement_timeout", statement_timeout),
            ("lock_timeout", lock_timeout),
        ):
            con.execute(
                text(f"SELECT set_config('{setting}', :timeout, true)"),
                {"timeout": f"{value}ms"},
            )
        statement, parameters = _totals_values(sql, rows)
        con.execute(text(statement), parameters)


def _totals_values(sql: str, rows: Rows) -> tuple[str, dict]:
    if len(rows) == 1:
        return sql, rows[0]
    # DBAPI executemany resets statement_timeout for every row. One INSERT
    # bounds the complete totals write with a single timeout.
    match = re.search(r"\bVALUES\s*(\([^)]*\))", sql, re.I)
    if match is None:
        raise ValueError("Expected a VALUES clause in totals upsert")
    values = []
    parameters = {}
    for index, row in enumerate(rows):

        def parameter_name(parameter: re.Match[str]) -> str:
            return f":{parameter.group(1)}_{index}"

        values.append(re.sub(r":(\w+)", parameter_name, match.group(1)))
        parameters.update(
            {f"{key}_{index}": value for key, value in row.items()}
        )
    statement = sql[: match.start(1)] + ", ".join(values) + sql[match.end(1) :]
    return statement, parameters


def read_to_store(
    engine, sql, store, name, params=None, schema=None, output=False
):
    """Stage a complete streamed RO attempt; rollback its disk rows on error."""
    with store.attempt():
        with engine.connect() as con:
            with con.begin():
                con.execute(text("SET TRANSACTION READ ONLY"))
                if schema is not None:
                    exists = con.execute(
                        text(
                            "SELECT 1 FROM pg_namespace WHERE nspname = :schema"
                        ),
                        {"schema": schema},
                    ).first()
                    if exists is None:
                        LOG.warning("Schema %s disappeared; skipping.", schema)
                        return []
                result = con.execution_options(
                    stream_results=True, yield_per=500
                ).execute(text(sql), params or {})
                try:
                    columns = list(result.keys())
                    rows = (dict(row) for row in result.mappings())
                    if output:
                        return store.output(name, columns, rows)
                    store.insert(name, rows)
                    return columns
                finally:
                    result.close()
