"""SQLite report definitions; PostgreSQL retains expensive tenant extraction."""

from pathlib import Path

from kokudaily.datasets import DEFINITIONS
from kokudaily.staging import fields

SQL_ROOT = Path(__file__).parent / "sql" / "sqlite"
INTEGER_COUNTS = {
    "cluster_count",
    "node_count",
    "infra_node_count",
    "control_plane_node_count",
    "worker_node_count",
    "pvc_count",
}


def totals_schema():
    result = {"date": "date"}
    for name in (
        "__cust_cloud_cost_report",
        "__cust_openshift_cost_report",
        "__cust_openshift_infra_report",
    ):
        for key, kind in fields(DEFINITIONS[name]).items():
            if key not in ("schema", "date", "architecture"):
                result["total_" + key] = (
                    "bigint" if key in INTEGER_COUNTS else kind
                )
    return result


TOTALS_SCHEMA = totals_schema()


def report_schema(filename):
    if filename == "cust_total_data.sql":
        return dict(TOTALS_SCHEMA, month="text")
    if filename == "cust_total_data_setup.sql":
        return TOTALS_SCHEMA
    table = {
        "cust_tag_report.sql": "__cust_tag_report",
        "cust_node_report.sql": "__cust_node_report",
        "cust_cost_model_report.sql": "__cust_cost_model_report",
        "cust_cloud_costs_data.sql": "__cust_cloud_cost_report",
        "cust_openshift_costs_data.sql": "__cust_openshift_cost_report",
        "cust_openshift_infra_data.sql": "__cust_openshift_infra_report",
    }.get(filename)
    if filename == "cust_cost_model_report_counts.sql":
        return {"domain": "array"}
    if not table:
        raise ValueError(f"No local report schema for {filename}")
    schema = fields(DEFINITIONS[table])
    if filename == "cust_openshift_infra_data.sql":
        schema = {"total_" + key: kind for key, kind in schema.items()}
    return schema


def query(store, filename):
    sql = (SQL_ROOT / filename).read_text()
    columns, rows = store.select(sql, report_schema(filename))
    return columns, rows


CUSTOMERS_SQL = """
WITH cust_non_redhat AS (
    SELECT customer_id,
           array_agg(DISTINCT substring(email FROM '@(.*)$')) AS domain
    FROM public.api_user
    WHERE substring(email FROM '@(.*)$') != 'redhat.com'
    GROUP BY customer_id
)
SELECT coalesce(c.account_id, 'unknown') AS account_id,
       c.org_id, c.schema_name, cnr.domain,
       (cnr.customer_id IS NOT NULL)::integer AS has_non_redhat
FROM public.api_customer c
LEFT JOIN cust_non_redhat cnr ON cnr.customer_id = c.id
WHERE c.org_id NOT IN ('11789772', '6340056', '11009103',
                      '1979710', '12667745', '12667749')
"""
ACTIVE_PROVIDERS_SQL = """
SELECT uuid::text AS uuid FROM public.api_provider
WHERE data_updated_timestamp >= now() - interval '48 HOURS'
"""
