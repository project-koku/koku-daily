"""Unit tests for per-schema setup helpers (COST-5794)."""

import unittest

from kokudaily.setup_runner import render_schema_sql
from kokudaily.setup_runner import validate_schema_name


class TestSetupRunner(unittest.TestCase):
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

    def test_render_schema_sql_uses_quoted_ident_when_provided(self):
        sql = "SELECT * FROM {schema}.t"
        self.assertEqual(
            render_schema_sql(sql, "org1234567", quoted_ident='"org1234567"'),
            'SELECT * FROM "org1234567".t',
        )


if __name__ == "__main__":
    unittest.main()
