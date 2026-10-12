"""Helpers for per-schema setup execution (COST-5794)."""

from __future__ import annotations

import logging
import re
from typing import Iterable
from typing import Optional
from typing import Sequence

from sqlalchemy import text

LOG = logging.getLogger(__name__)

SCHEMA_NAME_RE = re.compile(r"^(?:acct|org)[0-9A-Za-z_]+$")

# Hard-coded exclusions preserved from key_metrics setup SQL.
KEY_METRICS_EXCLUDE_SQL = "('acct6193296', 'acct6089719')"

TENANT_FILTER_ALL = "all"
TENANT_FILTER_OCP = "ocp"
TENANT_FILTER_KEY_METRICS = "key_metrics"


def validate_schema_name(schema_name: str) -> str:
    """Return schema_name if it matches acct*/org*; else raise."""
    if not SCHEMA_NAME_RE.match(schema_name):
        raise ValueError(f"Refusing unsafe schema name: {schema_name!r}")
    return schema_name


def quote_schema_ident(con, schema_name: str) -> str:
    """Validate schema_name then quote it via PostgreSQL quote_ident."""
    schema = validate_schema_name(schema_name)
    return con.execute(text("SELECT quote_ident(:n)"), {"n": schema}).scalar()


def render_schema_sql(
    sql_template: str,
    schema_name: str,
    quoted_ident: Optional[str] = None,
) -> str:
    """
    Substitute {schema} identifier placeholders after validation.

    Prefer passing quoted_ident from quote_schema_ident(con, …) at execute time.
    """
    schema = validate_schema_name(schema_name)
    ident = quoted_ident if quoted_ident is not None else schema
    return sql_template.replace("{schema}", ident)


def list_tenant_schemas(
    con,
    tenant_filter: str = TENANT_FILTER_ALL,
    provider_types: Optional[Sequence[str]] = None,
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
        sql += f"""
        AND t.schema_name NOT IN {KEY_METRICS_EXCLUDE_SQL}
        """

    sql += " ORDER BY t.schema_name"

    rows = con.execute(text(sql), params)
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
    params: Optional[dict] = None,
) -> None:
    """
    Run TEMP table init once, then per-schema INSERT + commit (fail-fast).

    TEMP tables use ON COMMIT PRESERVE ROWS (default), so commits keep rows.
    """
    bind = dict(params or {})
    con.execute(init_sql, bind)
    con.commit()

    schema_list = list(schemas)
    for idx, schema_name in enumerate(schema_list, start=1):
        schema = validate_schema_name(schema_name)
        quoted = quote_schema_ident(con, schema)
        rendered = text(
            render_schema_sql(
                per_schema_sql_template, schema, quoted_ident=quoted
            )
        )
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
