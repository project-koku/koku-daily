import csv
import datetime
import logging
import os
from tempfile import gettempdir
from typing import Any

from dateutil.relativedelta import relativedelta
from kokudaily.config import Config
from kokudaily.datasets import DEFINITIONS
from kokudaily.datasets import SETUP_TABLES
from kokudaily.engine import create_engine
from kokudaily.engine import DB_ENGINE
from kokudaily.replica import bind_datasets
from kokudaily.replica import merge_history
from kokudaily.replica import read_rows
from kokudaily.replica import read_schema
from kokudaily.replica import write_totals
from kokudaily.setup_runner import list_tenant_schemas
from kokudaily.setup_runner import TENANT_FILTER_ALL
from kokudaily.setup_runner import TENANT_FILTER_KEY_METRICS
from kokudaily.setup_runner import TENANT_FILTER_OCP
from pytz import UTC
from sqlalchemy import text

LOG = logging.getLogger(__name__)
USAGE_REPORT_PARAMS = {
    "start_time": datetime.datetime.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=UTC,
    )
    - relativedelta(months=1),
    "end_time": datetime.datetime.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=UTC,
    )
    + relativedelta(months=1),
    "provider_types": ["OCP"],  # MUST be a list!
}
LAST_3_MONTH_PARAMS = {
    "start_time": datetime.datetime.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=UTC,
    )
    - relativedelta(months=Config.KEY_METRICS_NUM_MONTHS),
    "end_time": datetime.datetime.now().replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=UTC,
    )
    + relativedelta(months=1),
}

REQUIRES: list[dict[str, list[dict[str, Any]]]] = [
    {
        # setup, teardown needed for customer-centric report(s)
        # Per-schema setup reads commit separately for each schema.
        "setup": [
            {
                "init_file": "sql/cust_cost_model_report_setup.sql",
                "per_schema_file": (
                    "sql/" "cust_cost_model_report_setup_schema.sql"
                ),
                "tenant_filter": TENANT_FILTER_ALL,
                "status": "",
                "frequency": "weekly",
                "sql_parameters": {},
            },
            {
                "init_file": "sql/cust_node_report_setup.sql",
                "per_schema_file": "sql/cust_node_report_setup_schema.sql",
                "tenant_filter": TENANT_FILTER_OCP,
                "status": "",
                "frequency": "weekly",
                "sql_parameters": USAGE_REPORT_PARAMS,
            },
            # {
            #     "file": "sql/cust_size_report_setup.sql",
            #     "status": "",
            #     "frequency": "weekly",
            #     "sql_parameters": USAGE_REPORT_PARAMS,
            # },
            {
                "init_file": "sql/cust_tag_report_setup.sql",
                "per_schema_file": "sql/cust_tag_report_setup_schema.sql",
                "tenant_filter": TENANT_FILTER_ALL,
                "status": "",
                "frequency": "daily",
                "sql_parameters": {},
            },
            {
                "init_file": "sql/key_metrics/cust_cloud_costs_data_setup.sql",
                "per_schema_file": (
                    "sql/key_metrics/cust_cloud_costs_data_setup_schema.sql"
                ),
                "tenant_filter": TENANT_FILTER_KEY_METRICS,
                "status": "",
                "frequency": "daily",
                "sql_parameters": LAST_3_MONTH_PARAMS,
            },
            {
                "init_file": (
                    "sql/key_metrics/" "cust_openshift_costs_data_setup.sql"
                ),
                "per_schema_file": (
                    "sql/key_metrics/"
                    "cust_openshift_costs_data_setup_schema.sql"
                ),
                "tenant_filter": TENANT_FILTER_KEY_METRICS,
                "status": "",
                "frequency": "daily",
                "sql_parameters": LAST_3_MONTH_PARAMS,
            },
            {
                "init_file": (
                    "sql/key_metrics/" "cust_openshift_infra_data_setup.sql"
                ),
                "per_schema_file": (
                    "sql/key_metrics/"
                    "cust_openshift_infra_data_setup_schema.sql"
                ),
                "tenant_filter": TENANT_FILTER_KEY_METRICS,
                "status": "",
                "frequency": "daily",
                "sql_parameters": LAST_3_MONTH_PARAMS,
            },
            {
                "file": "sql/key_metrics/cust_total_data_setup.sql",
                "status": "",
                "frequency": "daily",
                "sql_parameters": LAST_3_MONTH_PARAMS,
            },
        ],
        "teardown": [
            {"file": "sql/cust_cost_model_report_teardown.sql", "status": ""},
            {"file": "sql/cust_node_report_teardown.sql", "status": ""},
            {"file": "sql/cust_size_report_teardown.sql", "status": ""},
            {"file": "sql/cust_tag_report_teardown.sql", "status": ""},
            {
                "file": "sql/key_metrics/cust_cloud_costs_data_teardown.sql",
                "status": "",
            },
            {
                "file": "sql/key_metrics/cust_openshift_costs_data_teardown.sql",  # noqa: E501
                "status": "",
            },
            {
                "file": "sql/key_metrics/cust_openshift_infra_data_teardown.sql",  # noqa: E501
                "status": "",
            },
        ],
    }
]

WEEKLY_REPORTS: dict[str, dict[str, Any]] = {
    "cust_cost_model_report": {
        "file": "sql/cust_cost_model_report.sql",
        "target": "marketing",
    },
    "cust_cost_model_counts_report": {
        "file": "sql/cust_cost_model_report_counts.sql",
        "target": "marketing",
    },
    "cust_node_report": {
        "file": "sql/cust_node_report.sql",
        "target": "marketing",
    },
    # Disabling cust size report for now
    # "cust_size_report": {
    #     "file": "sql/cust_size_report.sql",
    #     "target": "engineering",
    # },
}

DAILY_REPORTS: dict[str, dict[str, Any]] = {
    "cust_tag_report": {
        "file": "sql/cust_tag_report.sql",
        "target": "engineering",
    },
    "customer_km_cloud_costs": {
        "file": "sql/key_metrics/cust_cloud_costs_data.sql",
        "target": "marketing",
        "sql_parameters": LAST_3_MONTH_PARAMS,
    },
    "customer_km_openshift_costs": {
        "file": "sql/key_metrics/cust_openshift_costs_data.sql",
        "target": "marketing",
        "sql_parameters": LAST_3_MONTH_PARAMS,
    },
    "customer_km_openshift_infra": {
        "file": "sql/key_metrics/cust_openshift_infra_data.sql",
        "target": "marketing",
        "sql_parameters": LAST_3_MONTH_PARAMS,
    },
    "customer_km_totals": {
        "file": "sql/key_metrics/cust_total_data.sql",
        "target": "marketing",
    },
}

REPORTS: dict[str, dict[str, Any]] = {
    "count_filtered_users": {
        "file": "sql/count_filtered_users.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
        "prometheus": {"type": "Gauge", "value": "count"},
    },
    "count_filtered_users_by_account": {
        "file": "sql/count_filtered_users_by_account.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
    },
    "count_filtered_users_by_domain": {
        "file": "sql/count_filtered_users_by_domain.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["domain"],
        },
    },
    "count_filtered_accounts": {
        "file": "sql/count_filtered_accounts.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
        "prometheus": {"type": "Gauge", "value": "count"},
    },
    "count_customers_by_setup_state": {
        "file": "sql/count_customers_by_setup_state.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
    },
    "list_filtered_accounts": {
        "file": "sql/list_filtered_accounts.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
    },
    "list_filtered_accounts_with_new_source_last_7_days": {
        "file": "sql/list_filtered_accounts_with_new_source_last_7_days.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
    },
    "count_providers_by_type": {
        "file": "sql/count_providers_by_type.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
    },
    "count_internal_providers_by_type": {
        "file": "sql/count_internal_providers_by_type.sql",
        "namespace": "hccm-prod",
        "target": "engineering",
    },
    "count_internal_providers_by_account": {
        "file": "sql/count_internal_providers_by_account.sql",
        "namespace": "hccm-prod",
        "target": "engineering",
    },
    "count_providers_by_filtered_account": {
        "file": "sql/count_providers_by_filtered_account.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["domain", "account_id", "org_id"],
        },
    },
    "count_providers_by_setup_state": {
        "file": "sql/count_providers_by_setup_state.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["setup_complete"],
        },
    },
    "count_providers_by_setup_state_and_filtered_account": {
        "file": "sql/count_providers_by_setup_state_and_filtered_account.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": [
                "domain",
                "account_id",
                "org_id",
                "type",
                "setup_complete",
            ],
        },
    },
    "count_openshift_clusters_by_infrastructure": {
        "file": "sql/count_openshift_clusters_by_infrastructure.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
    },
    "invalid_sources": {
        "file": "sql/invalid_sources.sql",
        "target": "engineering",
    },
    "count_invalid_sources": {
        "file": "sql/count_invalid_sources.sql",
        "target": "prometheus",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["account_id", "org_id", "source_type"],
        },
    },
    "orphaned_providers": {
        "file": "sql/orphaned_providers.sql",
        "target": "engineering",
    },
    "count_orphaned_providers": {
        "file": "sql/count_orphaned_providers.sql",
        "target": "prometheus",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["account_id", "org_id", "source_type"],
        },
    },
    "stale_providers": {
        "file": "sql/stale_providers.sql",
        "target": "engineering",
    },
    "count_stale_providers": {
        "file": "sql/count_stale_providers.sql",
        "target": "prometheus",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["account_id", "org_id", "source_type"],
        },
    },
    "active_providers": {
        "file": "sql/active_providers.sql",
        "target": "engineering",
    },
    "count_active_providers": {
        "file": "sql/count_active_providers.sql",
        "target": "prometheus",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["account_id", "org_id", "source_type"],
        },
    },
    "incomplete_manifests": {
        "file": "sql/incomplete_manifests.sql",
        "target": "engineering",
    },
    "count_incomplete_manifests": {
        "file": "sql/count_incomplete_manifests.sql",
        "target": "prometheus",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["account_id", "org_id", "source_type"],
        },
    },
    "empty_tenants": {
        "file": "sql/empty_tenants.sql",
        "target": "engineering",
    },
    "count_empty_tenants": {
        "file": "sql/count_empty_tenants.sql",
        "target": "prometheus",
        "prometheus": {"type": "Gauge", "value": "count"},
    },
    "count_airgapped_clusters": {
        "file": "sql/count_airgapped_clusters.sql",
        "target": "engineering",
    },
    "count_connected_clusters": {
        "file": "sql/count_connected_clusters.sql",
        "target": "engineering",
    },
    "count_community_clusters": {
        "file": "sql/count_community_clusters.sql",
        "target": "engineering",
    },
    "count_certified_clusters": {
        "file": "sql/count_certified_clusters.sql",
        "target": "engineering",
    },
    "count_errored_clusters": {
        "file": "sql/count_errored_clusters.sql",
        "target": "engineering",
    },
    "cust_providers": {
        "file": "sql/cust_providers.sql",
        "target": "marketing",
    },
}


def _read_sql_text(filename):
    """Read SQL file contents as a string (or None if missing)."""
    data_file = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(data_file) and os.path.isfile(data_file):
        with open(data_file) as file:
            return file.read()
    return None


def _required_sql(filename):
    sql = _read_sql_text(filename)
    if sql is None:
        raise FileNotFoundError(f"Missing report SQL: {filename}")
    return sql


def _run_setup_task(reader, task, cutoff):
    """Collect inputs with a separate RO transaction per schema."""
    parameters = dict(task.get("sql_parameters") or {})
    parameters["run_cutoff"] = cutoff
    with reader.connect() as con:
        with con.begin():
            con.execute(text("SET TRANSACTION READ ONLY"))
            schemas = list_tenant_schemas(
                con,
                task.get("tenant_filter", TENANT_FILTER_ALL),
                parameters.get("provider_types"),
            )
    sql = _required_sql(task["per_schema_file"])
    # These names come from the checked-in task descriptors, never user input.
    table = SETUP_TABLES[task["per_schema_file"]]
    rows = []
    complete = True
    for schema in schemas:
        result = read_schema(
            reader,
            sql,
            schema,
            dict(parameters, customer=schema),
            attempts=Config.REPLICA_RETRY_ATTEMPTS,
            delay=Config.REPLICA_RETRY_DELAY,
            check_exists=True,
        )
        rows.extend(result.rows)
        complete = complete and result.complete
    return table, rows, complete


def _collect_datasets(reader, run_weeklys):
    datasets = {}
    complete = True
    cutoff = None
    for require in REQUIRES:
        for task in require["setup"]:
            if task["frequency"] == "weekly" and not run_weeklys:
                continue
            if task["frequency"] == "daily" and not Config.RUN_DAILY_REPORTS:
                continue
            if task.get("per_schema_file"):
                if cutoff is None:
                    cutoff = read_rows(
                        reader, "SELECT clock_timestamp() AS cutoff"
                    ).rows[0]["cutoff"]
                table, rows, succeeded = _run_setup_task(reader, task, cutoff)
                datasets[table] = rows
                complete = complete and succeeded
            else:
                sql, params = bind_datasets(
                    _required_sql(task["file"]), datasets, DEFINITIONS
                )
                current = read_rows(reader, sql, params).rows
                if complete:
                    write_totals(
                        DB_ENGINE,
                        _required_sql(
                            "sql/key_metrics/cust_total_data_upsert.sql"
                        ),
                        current,
                        Config.REPORT_STATEMENT_TIMEOUT_MS,
                        Config.REPORT_LOCK_TIMEOUT_MS,
                    )
                else:
                    LOG.error(
                        "Reports incomplete: suppressing daily totals "
                        "persistence"
                    )
                history = read_rows(
                    reader, "SELECT * FROM public.__customer_total_data"
                ).rows
                datasets["__customer_total_data"] = merge_history(
                    history, current
                )
    return datasets


def _save_report(report_name, result, temp_dir):
    path = os.path.join(temp_dir, f"{report_name}.csv")
    data = [tuple(row[key] for key in result.columns) for row in result.rows]
    with open(path, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(result.columns)
        writer.writerows(data)
    return {
        "data": data,
        "columns": result.columns,
        "file": path,
        "data_dicts": result.rows,
    }


def run_reports(filter_target=None):
    """Compute reports on RO; acquire RW only for final daily upserts."""
    today = datetime.datetime.now(datetime.timezone.utc)
    run_weeklys = Config.WEEKLY_REPORT_SCHEDULED_DAY == today.weekday()
    selected = dict(REPORTS)
    if run_weeklys:
        selected.update(WEEKLY_REPORTS)
    if Config.RUN_DAILY_REPORTS:
        selected.update(DAILY_REPORTS)
    reader = create_engine(readonly=True)
    try:
        datasets = _collect_datasets(reader, run_weeklys)
        report_data: dict[str | None, dict[str, dict[str, Any]]] = {}
        temp_dir = os.path.join(gettempdir(), "reports")
        os.makedirs(temp_dir, exist_ok=True)
        for report_name, report in selected.items():
            namespace = report.get("namespace", Config.NAMESPACE)
            target = report.get("target", Config.NAMESPACE)
            if namespace != Config.NAMESPACE or (
                filter_target and target != filter_target
            ):
                continue
            sql, binds = bind_datasets(
                _required_sql(report["file"]), datasets, DEFINITIONS
            )
            parameters = dict(report.get("sql_parameters") or {})
            parameters.update(binds)
            result = read_rows(reader, sql, parameters)
            report_data.setdefault(target, {})[report_name] = _save_report(
                report_name, result, temp_dir
            )
        return report_data
    finally:
        reader.dispose()
