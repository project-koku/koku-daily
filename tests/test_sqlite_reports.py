"""Exact local report aggregation versus PostgreSQL, including sparse dates."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from kokudaily.datasets import DEFINITIONS
from kokudaily.local_reports import TOTALS_SCHEMA, query
from kokudaily.staging import Store, fields
from sqlalchemy import text


@pytest.mark.parametrize("empty", [False, True])
def test_sparse_and_null_aggregates_match_postgres(pg, tmp_path, empty):
    writer, _ = pg
    tables = (
        "__cust_cloud_cost_report",
        "__cust_openshift_cost_report",
        "__cust_openshift_infra_report",
    )
    with Store(tmp_path) as store, writer.connect() as con:
        for index, table in enumerate(tables):
            schema = fields(DEFINITIONS[table])
            store.create(table, schema)
            definition = DEFINITIONS[table]
            con.execute(text(f"CREATE TEMP TABLE {table} ({definition})"))
            if empty:
                continue
            rows = []
            # OCP costs have a date absent from both other inputs.
            for day in (
                date(2026, 2 if index == 1 else 1, 1),
                date(2026, 3, 2),
            ):
                for count in (1, 2):
                    row = {key: None for key in schema}
                    row.update(schema="org1", date=day)
                    for key, kind in schema.items():
                        if kind.startswith("numeric") and not key.endswith(
                            "memory_gb"
                        ):
                            row[key] = (
                                Decimal("123456789012345678901234567890.01")
                                if count == 1
                                else Decimal("-0.02")
                            )
                        elif kind in ("integer", "bigint"):
                            row[key] = count
                    rows.append(row)
            with store.attempt():
                store.insert(table, rows)
            keys = list(schema)
            statement = (
                f"INSERT INTO {table} VALUES ("
                + ",".join(":" + key for key in keys)
                + ")"
            )
            con.execute(text(statement), rows)
        for filename in (
            "cust_cloud_costs_data.sql",
            "cust_openshift_costs_data.sql",
            "cust_openshift_infra_data.sql",
            "cust_total_data_setup.sql",
        ):
            sql = Path("kokudaily/sql/key_metrics", filename).read_text()
            expected_result = con.execute(text(sql))
            expected_columns = list(expected_result.keys())
            expected = [dict(row) for row in expected_result.mappings()]
            columns, rows = query(store, filename)
            actual = list(rows)
            assert columns == expected_columns
            assert actual == expected
            for old, new in zip(expected, actual):
                for column in columns:
                    assert type(new[column]) is type(  # noqa: E721
                        old[column]
                    ), column
        _, totals = query(store, "cust_total_data_setup.sql")
        totals = list(totals)
        store.create("__customer_total_data", TOTALS_SCHEMA)
        with store.attempt():
            store.insert("__customer_total_data", totals)
        # Use unrestricted numeric in the test relation: SUM can exceed a source typmod.
        definition = ", ".join(
            key + " " + kind for key, kind in TOTALS_SCHEMA.items()
        )
        con.execute(
            text(f"CREATE TEMP TABLE __customer_total_data ({definition})")
        )
        if totals:
            statement = (
                "INSERT INTO __customer_total_data VALUES ("
                + ",".join(":" + key for key in TOTALS_SCHEMA)
                + ")"
            )
            con.execute(text(statement), totals)
        sql = Path("kokudaily/sql/key_metrics/cust_total_data.sql").read_text()
        expected = [dict(row) for row in con.execute(text(sql)).mappings()]
        _, rows = query(store, "cust_total_data.sql")
        assert list(rows) == expected


def test_unknown_local_query_schema_fails_closed():
    from kokudaily.local_reports import report_schema

    with pytest.raises(ValueError, match="No local report schema"):
        report_schema("unrecognized.sql")
