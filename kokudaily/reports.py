import copy
import csv
import os
from tempfile import gettempdir

from kokudaily.config import Config
from kokudaily.engine import DB_ENGINE


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
    "list_filtered_accounts": {
        "file": "sql/list_filtered_accounts.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
    },
    "count_providers_by_filtered_account": {
        "file": "sql/count_providers_by_filtered_account.sql",
        "namespace": "hccm-prod",
        "target": "marketing",
        "prometheus": {
            "type": "Gauge",
            "value": "count",
            "labels": ["domain", "account_id"],
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
            "labels": ["domain", "account_id", "type", "setup_complete"],
        },
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
            "labels": ["account_id", "source_type"],
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
            "labels": ["account_id", "source_type"],
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
            "labels": ["account_id", "source_type"],
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
            "labels": ["account_id", "source_type"],
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
}


def _read_sql(filename):
    """Read SQL data from file."""
    data = None
    data_file = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(data_file) and os.path.isfile(data_file):
        with open(data_file, "r") as file:
            data = file.read()
    return data


def run_reports(filter_target=None):
    """Run the reports."""
    db = DB_ENGINE
    report_data = {}
    tmp = gettempdir()
    temp_dir = os.path.join(tmp, "reports")
    os.makedirs(temp_dir, exist_ok=True)
    with db.connect() as con:
        for report_name, report_sql_obj in REPORTS.items():
            namespace = report_sql_obj.get("namespace", Config.NAMESPACE)
            target = report_sql_obj.get("target", Config.NAMESPACE)
            report_sql_file = report_sql_obj.get("file")
            valid_target = (not filter_target) or target == filter_target
            if namespace == Config.NAMESPACE and valid_target:
                report_sql = _read_sql(report_sql_file)
                rs = con.execute(report_sql)
                keys = con.execute(report_sql).keys()
                data = []
                data_dicts = []
                tempfile = os.path.join(temp_dir, f"{report_name}.csv")
                with open(tempfile, "w", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(keys)
                    for row in rs:
                        writer.writerow(row)
                        row_copy = copy.deepcopy(row)
                        data.append(row_copy)
                        row_dict = {}
                        for idx, row_item in enumerate(row):
                            column = keys[idx]
                            row_dict[column] = row_item
                        data_dicts.append(row_dict)
                target_obj = report_data.get(target, {})
                target_obj[report_name] = {
                    "data": data,
                    "columns": keys,
                    "file": tempfile,
                    "data_dicts": data_dicts,
                }
                report_data[target] = target_obj

    return report_data
