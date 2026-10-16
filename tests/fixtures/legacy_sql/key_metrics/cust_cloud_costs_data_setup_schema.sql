INSERT INTO __cust_cloud_cost_report (
    schema,
    date,
    aws_unblended_cost,
    aws_calculated_amortized_cost,
    azure_pretax_cost,
    gcp_unblended_cost,
    gcp_total
)
WITH schemas AS (
    SELECT
        :customer AS "customer",
        generate_series(date_trunc('month', CAST(:start_time AS date)), CAST(:run_cutoff AS timestamptz), '1 day')::date AS "date"
),
aws_costs_currencies AS (
    SELECT
        :customer AS "customer",
        usage_start AS "date",
        SUM(unblended_cost) AS "unblended_cost",
        SUM(calculated_amortized_cost) AS "calculated_amortized_cost",
        currency_code AS "currency"
    FROM
        {schema}.reporting_aws_cost_summary_p
    WHERE
        usage_start >= CAST(:start_time AS date)
        AND usage_start < CAST(:end_time AS date)
    GROUP BY currency, usage_start
),
aws_costs AS (
    SELECT
        :customer AS "customer",
        date AS "date",
        SUM(unblended_cost / pae.exchange_rate) AS "aws_unblended_cost",
        SUM(calculated_amortized_cost / pae.exchange_rate) AS "aws_calculated_amortized_cost"
    FROM aws_costs_currencies acc
    JOIN public.api_exchangerates pae ON LOWER(pae.currency_type)=LOWER(acc.currency)
    GROUP BY date
),
azure_costs_currencies AS (
    SELECT
        :customer AS "customer",
        usage_start AS "date",
        SUM(pretax_cost) AS "pretax_cost",
        currency AS "currency"
    FROM
        {schema}.reporting_azure_cost_summary_p
    WHERE
        usage_start >= CAST(:start_time AS date)
        AND usage_start < CAST(:end_time AS date)
    GROUP BY currency, usage_start
),
azure_costs AS (
    SELECT
        :customer AS "customer",
        date AS "date",
        SUM(pretax_cost / pae.exchange_rate) AS "azure_pretax_cost"
    FROM azure_costs_currencies azcc
    JOIN public.api_exchangerates pae ON LOWER(pae.currency_type)=LOWER(azcc.currency)
    GROUP BY date
),
gcp_costs_currencies AS (
    SELECT
        :customer AS "customer",
        usage_start AS "date",
        SUM(unblended_cost) AS "unblended_cost",
        SUM(credit_amount) AS "credit_amount",
        currency AS "currency"
    FROM
        {schema}.reporting_gcp_cost_summary_p
    WHERE
        usage_start >= CAST(:start_time AS date)
        AND usage_start < CAST(:end_time AS date)
    GROUP BY currency, usage_start
),
gcp_costs AS (
    SELECT
        :customer AS "customer",
        date AS "date",
        SUM(unblended_cost / pae.exchange_rate) AS "gcp_unblended_cost",
        SUM(unblended_cost / pae.exchange_rate + credit_amount / pae.exchange_rate) AS "gcp_total"
    FROM gcp_costs_currencies gcc
    JOIN public.api_exchangerates pae ON LOWER(pae.currency_type)=LOWER(gcc.currency)
    GROUP BY date
)
SELECT
    s.customer AS "schema",
    s.date AS "date",
    awc.aws_unblended_cost AS "aws_unblended_cost",
    awc.aws_calculated_amortized_cost AS "aws_calculated_amortized_cost",
    azc.azure_pretax_cost AS "azure_pretax_cost",
    gc.gcp_unblended_cost AS "gcp_unblended_cost",
    gc.gcp_total AS "gcp_total"
FROM
    schemas s
    FULL OUTER JOIN aws_costs awc USING (customer, date)
    FULL OUTER JOIN azure_costs azc USING (customer, date)
    FULL OUTER JOIN gcp_costs gc USING (customer, date)
ORDER BY date
;
