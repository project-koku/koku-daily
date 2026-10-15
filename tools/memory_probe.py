"""Measure client intermediate retention and JSON serialization, not PG RAM."""

import argparse
import json
import re
import resource
import sys
from datetime import date
from datetime import timedelta
from decimal import Decimal

from kokudaily.datasets import DEFINITIONS
from kokudaily.replica import bind_datasets


def memory_mib():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1024 * 1024 if sys.platform == "darwin" else 1024)


def value_for(column, kind, tenant, index):
    if kind.startswith("numeric"):
        return Decimal(f"{tenant * 10 + index}.25")
    if kind == "date":
        return date(2026, 1, 1) + timedelta(days=index % 90)
    if kind in ("bigint", "integer"):
        return index % 101
    if kind == "jsonb":
        return {"key": f"value-{tenant}-{index}"}
    if column in ("schema", "customer"):
        return f"org{tenant}"
    return f"{column}-{tenant}-{index}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenants", type=int, required=True)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--nodes", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.tenants <= 500 or min(args.days, args.nodes) < 1:
        raise ValueError("Probe is bounded to 1..500 tenants")
    baseline = memory_mib()
    datasets = {}
    for table, definition in DEFINITIONS.items():
        if table == "__customer_total_data":
            continue
        per_tenant = args.days
        if table == "__cust_node_report":
            per_tenant = args.nodes * 3
        elif table == "__cust_openshift_infra_report":
            per_tenant *= 3
        elif table == "__cust_cost_model_report":
            per_tenant = 2
        elif table == "__cust_tag_report":
            per_tenant = 1
        columns = re.findall(r"(\w+)\s+(numeric\([^)]*\)|\w+)", definition)
        if not columns:
            raise RuntimeError("Invalid intermediate definition")
        datasets[table] = [
            {
                column: value_for(column, kind, tenant, index)
                for column, kind in columns
            }
            for tenant in range(args.tenants)
            for index in range(per_tenant)
        ]
    retained = memory_mib()
    _, binds = bind_datasets(
        "SELECT * FROM __cust_cloud_cost_report, "
        "__cust_openshift_cost_report, __cust_openshift_infra_report",
        datasets,
        DEFINITIONS,
    )
    print(
        json.dumps(
            {
                "tenants": args.tenants,
                "days": args.days,
                "nodes_per_tenant": args.nodes,
                "intermediate_rows": sum(map(len, datasets.values())),
                "baseline_peak_mib": round(baseline, 1),
                "retained_peak_mib": round(retained, 1),
                "serialized_peak_mib": round(memory_mib(), 1),
                "bound_payload_mib": round(
                    sum(len(v.encode()) for v in binds.values()) / 1024**2, 1
                ),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
