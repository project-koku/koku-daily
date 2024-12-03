import csv
import datetime
import logging
import os
from tempfile import gettempdir

from dateutil.relativedelta import relativedelta
from kokudaily.config import Config
from kokudaily.engine import DB_ENGINE
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

REQUIRES = [
    {
        # setup, teardown needed for customer-centric report(s)
        "setup": [
            {
                "file": "sql/cust_cost_model_report_setup.sql",
                "status": "",
                "frequency": "weekly",
                "sql_parameters": {},
            },
            {
                "file": "sql/cust_node_report_setup.sql",
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
                "file": "sql/cust_tag_report_setup.sql",
                "status": "",
                "frequency": "daily",
                "sql_parameters": {},
            },
            {
                "file": "sql/key_metrics/cust_cloud_costs_data_setup.sql",
                "status": "",
                "frequency": "daily",
                "sql_parameters": LAST_3_MONTH_PARAMS,
            },
            {
                "file": "sql/key_metrics/cust_openshift_costs_data_setup.sql",
                "status": "",
                "frequency": "daily",
                "sql_parameters": LAST_3_MONTH_PARAMS,
            },
            {
                "file": "sql/key_metrics/cust_openshift_infra_data_setup.sql",
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

WEEKLY_REPORTS = {
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

DAILY_REPORTS = {
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

REPORTS = {
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


def _read_sql(filename):
    """Read SQL data from file."""
    data = None
    data_file = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(data_file) and os.path.isfile(data_file):
        with open(data_file) as file:
            data = file.read()
    return text(data)


def run_reports(filter_target=None):
    """Run the reports."""
    today = datetime.datetime.now(datetime.timezone.utc)
    run_weeklys = Config.WEEKLY_REPORT_SCHEDULED_DAY == today.weekday()
    if run_weeklys:
        REPORTS.update(WEEKLY_REPORTS)
    if Config.RUN_DAILY_REPORTS:
        REPORTS.update(DAILY_REPORTS)
    db = DB_ENGINE
    report_data = {}
    tmp = gettempdir()
    temp_dir = os.path.join(tmp, "reports")
    os.makedirs(temp_dir, exist_ok=True)
    with db.connect() as con:

        # Do any setup needed
        LOG.info("Running setup...")
        for require in REQUIRES:
            for task in require["setup"]:
                if task["frequency"] == "weekly" and not run_weeklys:
                    # We only run this task once a week, skip setup.
                    continue
                if (
                    task["frequency"] == "daily"
                    and not Config.RUN_DAILY_REPORTS
                ):
                    # We only run this task once a day, skip setup.
                    continue
                if task["status"] != "complete":
                    task_file = task["file"]
                    task_parameters = task.get("sql_parameters")
                    if task_file:
                        LOG.info(f"    Executing setup task {task_file}...")
                        task_sql = _read_sql(task_file)
                        con.execute(task_sql, task_parameters)
                    task["status"] = "complete"

        for report_name, report_sql_obj in REPORTS.items():
            namespace = report_sql_obj.get("namespace", Config.NAMESPACE)
            target = report_sql_obj.get("target", Config.NAMESPACE)
            report_sql_file = report_sql_obj.get("file")
            valid_target = (not filter_target) or target == filter_target
            if namespace == Config.NAMESPACE and valid_target:
                LOG.info(f"report_sql_file={report_sql_file}.")
                report_sql = _read_sql(report_sql_file)
                report_sql_params = report_sql_obj.get("sql_parameters")
                rs = con.execute(report_sql, report_sql_params)
                keys = rs.keys()
                data = []
                data_dicts = []
                tempfile = os.path.join(temp_dir, f"{report_name}.csv")
                LOG.debug(tempfile)
                with open(tempfile, "w", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(keys)
                    for row in rs:
                        writer.writerow(row)
                        data.append(row)
                        data_dicts.append(row._asdict())
                target_obj = report_data.get(target, {})
                target_obj[report_name] = {
                    "data": data,
                    "columns": keys,
                    "file": tempfile,
                    "data_dicts": data_dicts,
                }
                report_data[target] = target_obj

        # tear down any setups
        LOG.info("Running teardown...")
        for require in REQUIRES:
            for task in require["teardown"]:
                task_file = task["file"]
                if task_file:
                    LOG.info(f"    Executing teardown task {task_file}...")
                    task_sql = _read_sql(task_file)
                    con.execute(task_sql)
                task["status"] = "complete"

    return report_data
