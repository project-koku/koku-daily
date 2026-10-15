"""Helpers for per-schema setup execution (COST-5794)."""

from __future__ import annotations

import logging
import re
from typing import Iterable
from typing import Sequence

from sqlalchemy import bindparam
from sqlalchemy import text

LOG = logging.getLogger(__name__)

SCHEMA_NAME_RE = re.compile(r"^(?:acct|org)[0-9A-Za-z_]+$")

# Hard-coded exclusions preserved from key_metrics setup SQL.
KEY_METRICS_EXCLUDE_SCHEMAS = ("acct6193296", "acct6089719")

TENANT_FILTER_ALL = "all"
TENANT_FILTER_OCP = "ocp"
TENANT_FILTER_KEY_METRICS = "key_metrics"


def validate_schema_name(schema_name: str) -> str:
    """Return schema_name if it matches acct*/org*; else raise."""
    if not SCHEMA_NAME_RE.match(schema_name):
        raise ValueError(f"Refusing unsafe schema name: {schema_name!r}")
    return schema_name


def render_schema_sql(sql_template: str, schema_name: str) -> str:
    """Substitute {schema} after validating the name is a safe identifier."""
    schema = validate_schema_name(schema_name)
    return sql_template.replace("{schema}", schema)


def list_tenant_schemas(
    con,
    tenant_filter: str = TENANT_FILTER_ALL,
    provider_types: Sequence[str] | None = None,
) -> list[str]:
    """List tenant schemas using the same filters as the former DO loops."""
    params: dict = {}
    sql = """
        SELECT DISTINCT t.schema_name
        FROM   public.api_tenant t
        JOIN   pg_namespace n
        ON     n.nspname = t.schema_name
        JOIN   public.api_customer c
        ON     c.schema_name = t.schema_name
    """
    if tenant_filter == TENANT_FILTER_OCP:
        if not provider_types:
            raise ValueError("provider_types required for tenant_filter='ocp'")
        sql += """
        JOIN   public.api_provider p
        ON     p.customer_id = c.id
        AND    p.type = ANY(:provider_types)
        """
        params["provider_types"] = list(provider_types)

    sql += """
        WHERE  (t.schema_name ~ '^acct' OR t.schema_name ~ '^org')
    """
    if tenant_filter == TENANT_FILTER_KEY_METRICS:
        sql += """
        AND t.schema_name NOT IN :exclude_schemas
        """
        params["exclude_schemas"] = list(KEY_METRICS_EXCLUDE_SCHEMAS)

    sql += " ORDER BY t.schema_name"

    if tenant_filter == TENANT_FILTER_KEY_METRICS:
        stmt = text(sql).bindparams(
            bindparam("exclude_schemas", expanding=True)
        )
    else:
        stmt = text(sql)

    rows = con.execute(stmt, params)
    schemas = [validate_schema_name(row[0]) for row in rows]
    LOG.info(
        "Listed %s tenant schemas (filter=%s)", len(schemas), tenant_filter
    )
    return schemas


def run_per_schema_setup(
    con,
    init_sql,
    per_schema_sql_template: str,
    schemas: Iterable[str],
    params: dict | None = None,
) -> None:
    """
    Run TEMP table init once, then per-schema INSERT + commit (fail-fast).

    TEMP tables use ON COMMIT PRESERVE ROWS (default), so commits keep rows.

    Captures a single ``run_cutoff`` (wall clock) before the tenant loop so
    SQL that previously used ``now()`` inside one DO-loop transaction keeps a
    stable date series across per-schema commits. Skips schemas that disappear
    between listing and execution; other errors remain fail-fast.
    """
    bind = dict(params or {})
    con.execute(init_sql, bind)
    con.commit()

    # Stable cutoff for generate_series / date bounds across per-schema commits
    # (replaces transaction-scoped now() from the former DO loops).
    if "run_cutoff" not in bind:
        bind["run_cutoff"] = con.execute(
            text("SELECT clock_timestamp()")
        ).scalar()

    schema_list = list(schemas)
    for idx, schema_name in enumerate(schema_list, start=1):
        schema = validate_schema_name(schema_name)
        exists = con.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :n"),
            {"n": schema},
        ).scalar()
        if not exists:
            LOG.warning(
                "Schema %s no longer in pg_namespace; skipping.", schema
            )
            continue
        rendered = text(render_schema_sql(per_schema_sql_template, schema))
        schema_bind = dict(bind)
        schema_bind["customer"] = schema
        LOG.info(
            "      [%s/%s] Executing per-schema setup for %s...",
            idx,
            len(schema_list),
            schema,
        )
        con.execute(rendered, schema_bind)
        con.commit()
