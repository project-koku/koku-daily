"""Unit tests for per-schema setup helpers (COST-5794)."""

import unittest
from unittest import mock

from kokudaily.setup_runner import KEY_METRICS_EXCLUDE_SCHEMAS
from kokudaily.setup_runner import list_tenant_schemas
from kokudaily.setup_runner import render_schema_sql
from kokudaily.setup_runner import run_per_schema_setup
from kokudaily.setup_runner import TENANT_FILTER_ALL
from kokudaily.setup_runner import TENANT_FILTER_KEY_METRICS
from kokudaily.setup_runner import TENANT_FILTER_OCP
from kokudaily.setup_runner import validate_schema_name
from sqlalchemy import text


class FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalar(self):
        if not self._rows:
            return None
        row = self._rows[0]
        return row[0] if isinstance(row, (tuple, list)) else row

    def __iter__(self):
        return iter(self._rows)


class FakeConnection:
    """Records execute/commit calls for run_per_schema_setup tests."""

    def __init__(self, existing_schemas=None, cutoff="2026-10-13T12:00:00Z"):
        self.existing_schemas = set(existing_schemas or [])
        self.cutoff = cutoff
        self.executes = []
        self.commits = 0

    def execute(self, statement, params=None):
        params = dict(params or {})
        sql = str(statement)
        self.executes.append((sql, params))
        if "clock_timestamp" in sql:
            return FakeResult([(self.cutoff,)])
        if "pg_namespace WHERE nspname" in sql:
            name = params.get("n")
            if name in self.existing_schemas:
                return FakeResult([(1,)])
            return FakeResult([])
        return FakeResult([])

    def commit(self):
        self.commits += 1


class TestSetupRunnerHelpers(unittest.TestCase):
    def test_validate_schema_name_accepts_org_and_acct(self):
        self.assertEqual(validate_schema_name("org1234567"), "org1234567")
        self.assertEqual(validate_schema_name("acct6193296"), "acct6193296")

    def test_validate_schema_name_rejects_unsafe(self):
        with self.assertRaises(ValueError):
            validate_schema_name("public")
        with self.assertRaises(ValueError):
            validate_schema_name('org1"; DROP TABLE x; --')

    def test_render_schema_sql_substitutes_identifier(self):
        sql = "SELECT * FROM {schema}.reporting_ocptags_values"
        self.assertEqual(
            render_schema_sql(sql, "org1234567"),
            "SELECT * FROM org1234567.reporting_ocptags_values",
        )


class TestListTenantSchemas(unittest.TestCase):
    def test_all_filter_sql(self):
        con = mock.Mock()
        con.execute.return_value = FakeResult([("org1",), ("acct2",)])
        schemas = list_tenant_schemas(con, tenant_filter=TENANT_FILTER_ALL)
        self.assertEqual(schemas, ["org1", "acct2"])
        stmt, params = con.execute.call_args[0][0], con.execute.call_args[0][1]
        sql = str(stmt)
        self.assertIn("api_tenant", sql)
        self.assertNotIn("api_provider", sql)
        self.assertNotIn("exclude_schemas", params)

    def test_ocp_filter_requires_provider_types_and_joins(self):
        con = mock.Mock()
        con.execute.return_value = FakeResult([("org1",)])
        with self.assertRaises(ValueError):
            list_tenant_schemas(con, tenant_filter=TENANT_FILTER_OCP)
        schemas = list_tenant_schemas(
            con, tenant_filter=TENANT_FILTER_OCP, provider_types=["OCP"]
        )
        self.assertEqual(schemas, ["org1"])
        stmt, params = con.execute.call_args[0][0], con.execute.call_args[0][1]
        sql = str(stmt)
        self.assertIn("api_provider", sql)
        self.assertIn("ANY(:provider_types)", sql)
        self.assertEqual(params["provider_types"], ["OCP"])

    def test_key_metrics_filter_binds_exclusions(self):
        con = mock.Mock()
        con.execute.return_value = FakeResult([("org1",)])
        schemas = list_tenant_schemas(
            con, tenant_filter=TENANT_FILTER_KEY_METRICS
        )
        self.assertEqual(schemas, ["org1"])
        stmt, params = con.execute.call_args[0][0], con.execute.call_args[0][1]
        sql = str(stmt)
        self.assertIn("NOT IN", sql)
        self.assertEqual(
            params["exclude_schemas"], list(KEY_METRICS_EXCLUDE_SCHEMAS)
        )


class TestRunPerSchemaSetup(unittest.TestCase):
    def test_commits_after_each_schema_and_binds_customer_cutoff(self):
        con = FakeConnection(existing_schemas={"org1", "org2"})
        init = text("CREATE TEMP TABLE t (x int)")
        per = "INSERT INTO t SELECT 1 FROM {schema}.foo WHERE c = :customer"
        run_per_schema_setup(con, init, per, ["org1", "org2"], {"start": 1})

        # init commit + 2 schema commits
        self.assertEqual(con.commits, 3)
        # last two executes with customer should be the per-schema inserts
        per_execs = [
            (sql, params)
            for sql, params in con.executes
            if "INSERT INTO t" in sql
        ]
        self.assertEqual(len(per_execs), 2)
        self.assertEqual(per_execs[0][1]["customer"], "org1")
        self.assertEqual(per_execs[1][1]["customer"], "org2")
        self.assertEqual(per_execs[0][1]["run_cutoff"], con.cutoff)
        self.assertEqual(per_execs[1][1]["run_cutoff"], con.cutoff)
        self.assertIn("org1.foo", per_execs[0][0])
        self.assertIn("org2.foo", per_execs[1][0])

    def test_skips_missing_schema_keeps_fail_fast_for_others(self):
        con = FakeConnection(existing_schemas={"org2"})
        init = text("CREATE TEMP TABLE t (x int)")
        per = "INSERT INTO t SELECT 1 FROM {schema}.foo"
        run_per_schema_setup(con, init, per, ["org1", "org2"])

        per_execs = [
            (sql, params)
            for sql, params in con.executes
            if "INSERT INTO t" in sql
        ]
        self.assertEqual(len(per_execs), 1)
        self.assertEqual(per_execs[0][1]["customer"], "org2")
        # init + one surviving schema
        self.assertEqual(con.commits, 2)


if __name__ == "__main__":
    unittest.main()
