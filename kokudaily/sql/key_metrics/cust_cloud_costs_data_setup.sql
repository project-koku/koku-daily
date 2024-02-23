DROP TABLE IF EXISTS __cust_cloud_cost_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_cloud_cost_report (
    id serial,
    aws_unblended_cost numeric(33, 2),
    aws_calculated_amortized_cost numeric(33, 2),
    azure_pretax_cost numeric(33, 2),
    gcp_unblended_cost numeric(33, 2),
    gcp_total numeric(33, 2),
    oci_cost numeric(33, 2)
);

-- loop construct
DO $BODY$
DECLARE
    schema_rec record;
    stmt_tmpl text = '
INSERT INTO __cust_cloud_cost_report (
    aws_unblended_cost,
    aws_calculated_amortized_cost,
    azure_pretax_cost,
    gcp_unblended_cost,
    gcp_total,
    oci_cost)
WITH aws_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        SUM(unblended_cost) AS "aws_unblended_cost",
        SUM(calculated_amortized_cost) AS "aws_calculated_amortized_cost"
    FROM
        %%1$s.reporting_aws_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
),
azure_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        SUM(pretax_cost) AS "azure_pretax_cost"
    FROM
        %%1$s.reporting_azure_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
),
gcp_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        SUM(unblended_cost) AS "gcp_unblended_cost",
        SUM(unblended_cost + credit_amount) AS "gcp_total"
    FROM
        %%1$s.reporting_gcp_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
),
oci_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        SUM(cost) AS "oci_cost"
    FROM
        %%1$s.reporting_oci_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
)
SELECT
    -- awc.customer AS "customer", -- customer is used for grouping, but left off report for anonymity
    awc.aws_unblended_cost AS "aws_unblended_cost",
    awc.aws_calculated_amortized_cost AS "aws_calculated_amortized_cost",
    azc.azure_pretax_cost AS "azure_pretax_cost",
    gc.gcp_unblended_cost AS "gcp_unblended_cost",
    gc.gcp_total AS "gcp_total",
    oc.oci_cost AS "oci_cost"
FROM
    aws_costs awc
    JOIN azure_costs azc ON awc.customer = azc.customer
    JOIN gcp_costs gc ON awc.customer = gc.customer
    JOIN oci_costs oc ON awc.customer = oc.customer
';
BEGIN
    FOR schema_rec IN SELECT DISTINCT
        t.schema_name
    FROM
        public.api_tenant t
        JOIN pg_namespace n ON n.nspname = t.schema_name
        JOIN public.api_customer c ON c.schema_name = t.schema_name
    WHERE
        t.schema_name ~ '^acct'
        OR t.schema_name ~ '^org'
    ORDER BY
        t.schema_name
    LOOP
        EXECUTE format(stmt_tmpl, schema_rec.schema_name, %(start_time)s, %(end_time)s);
    END LOOP;
END $BODY$ LANGUAGE plpgsql;
