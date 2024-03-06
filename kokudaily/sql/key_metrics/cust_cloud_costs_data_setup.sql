DROP TABLE IF EXISTS __cust_cloud_cost_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_cloud_cost_report (
    id serial,
    month date,
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
    month,
    aws_unblended_cost,
    aws_calculated_amortized_cost,
    azure_pretax_cost,
    gcp_unblended_cost,
    gcp_total,
    oci_cost
)
WITH aws_costs_currencies AS (
    SELECT
        ''%%1$s'' AS "customer",
        DATE_TRUNC(''month'', usage_start) AS "month",
        SUM(unblended_cost) AS "unblended_cost",
        SUM(calculated_amortized_cost) AS "calculated_amortized_cost",
        currency_code AS "currency"
    FROM
        %%1$s.reporting_aws_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
    GROUP BY currency, month
),
aws_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        month AS "month",
        SUM(unblended_cost * pae.exchange_rate) AS "aws_unblended_cost",
        SUM(calculated_amortized_cost * pae.exchange_rate) AS "aws_calculated_amortized_cost"
    FROM aws_costs_currencies acc
    JOIN public.api_exchangerates pae ON LOWER(pae.currency_type)=LOWER(acc.currency)
    GROUP BY month
),
azure_costs_currencies AS (
    SELECT
        ''%%1$s'' AS "customer",
        DATE_TRUNC(''month'', usage_start) AS "month",
        SUM(pretax_cost) AS "pretax_cost",
        currency AS "currency"
    FROM
        %%1$s.reporting_azure_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
    GROUP BY currency, month
),
azure_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        month AS "month",
        SUM(pretax_cost * pae.exchange_rate) AS "azure_pretax_cost"
    FROM azure_costs_currencies azcc
    JOIN public.api_exchangerates pae ON LOWER(pae.currency_type)=LOWER(azcc.currency)
    GROUP BY month
),
gcp_costs_currencies AS (
    SELECT
        ''%%1$s'' AS "customer",
        DATE_TRUNC(''month'', usage_start) AS "month",
        SUM(unblended_cost) AS "unblended_cost",
        SUM(credit_amount) AS "credit_amount",
        currency AS "currency"
    FROM
        %%1$s.reporting_gcp_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
    GROUP BY currency, month
),
gcp_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        month AS "month",
        SUM(unblended_cost * pae.exchange_rate) AS "gcp_unblended_cost",
        SUM(unblended_cost * pae.exchange_rate + credit_amount * pae.exchange_rate) AS "gcp_total"
    FROM gcp_costs_currencies gcc
    JOIN public.api_exchangerates pae ON LOWER(pae.currency_type)=LOWER(gcc.currency)
    GROUP BY month
),
oci_costs_currencies AS (
    SELECT
        ''%%1$s'' AS "customer",
        DATE_TRUNC(''month'', usage_start) AS "month",
        SUM(cost) AS "cost",
        currency AS "currency"
    FROM
        %%1$s.reporting_oci_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
    GROUP BY currency, month
),
oci_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        month AS "month",
        SUM(cost * pae.exchange_rate) AS "oci_cost"
    FROM oci_costs_currencies oc
    JOIN public.api_exchangerates pae ON LOWER(pae.currency_type)=LOWER(oc.currency)
    GROUP BY month
)
SELECT
    -- awc.customer AS "customer", -- customer is used for grouping, but left off report for anonymity
    month AS "month",
    awc.aws_unblended_cost AS "aws_unblended_cost",
    awc.aws_calculated_amortized_cost AS "aws_calculated_amortized_cost",
    azc.azure_pretax_cost AS "azure_pretax_cost",
    gc.gcp_unblended_cost AS "gcp_unblended_cost",
    gc.gcp_total AS "gcp_total",
    oc.oci_cost AS "oci_cost"
FROM
    aws_costs awc
    FULL OUTER JOIN azure_costs azc USING (customer, month)
    FULL OUTER JOIN gcp_costs gc USING (customer, month)
    FULL OUTER JOIN oci_costs oc USING (customer, month)
ORDER BY month
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
