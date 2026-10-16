"""Short read-only transactions and bounded final writes for reporting."""

import json
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from kokudaily.setup_runner import render_schema_sql
from kokudaily.setup_runner import validate_schema_name
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

LOG = logging.getLogger(__name__)
Rows = list[dict[str, Any]]


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


def merge_history(history: Rows, current: Rows) -> Rows:
    """Overlay this run's daily totals without waiting for WAL replay."""
    merged = {row["date"]: row for row in history}
    merged.update({row["date"]: row for row in current})
    return [merged[day] for day in sorted(merged)]


def _json_value(value: Any) -> str:
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Unsupported report value type: {type(value).__name__}")


def bind_datasets(
    sql: str, datasets: dict[str, Rows], definitions: dict[str, str]
) -> tuple[str, dict]:
    """Supply Python intermediates as typed read-only relations on RO."""
    relations: list[str] = []
    params = {}
    for name, rows in datasets.items():
        if re.search(r"\b" + re.escape(name) + r"\b", sql):
            parameter = f"dataset_{len(relations)}"
            if name == "__customer_total_data":
                relation = (
                    "jsonb_populate_recordset("
                    "NULL::public.__customer_total_data, "
                    f"CAST(:{parameter} AS jsonb))"
                )
            else:
                relation = (
                    f"jsonb_to_recordset(CAST(:{parameter} AS jsonb)) "
                    f"AS data({definitions[name]})"
                )
            relations.append(f"{name} AS (SELECT * FROM {relation})")
            params[parameter] = json.dumps(rows, default=_json_value)
    if relations:
        sql = (
            "WITH "
            + ", ".join(relations)
            + " SELECT * FROM (\n"
            + sql.rstrip().rstrip(";")
            + "\n) AS report"
        )
    return sql, params


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
