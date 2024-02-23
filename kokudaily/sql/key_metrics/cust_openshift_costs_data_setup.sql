DROP TABLE IF EXISTS __cust_openshift_cost_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_openshift_cost_report (
    id serial,
    total_infrastructure_raw_cost numeric(33, 2),
    total_cost_model_costs numeric(33, 2),
    infra_total_cost_model numeric(33, 2),
    infra_cost_model_cpu_cost numeric(33, 2),
    infra_cost_model_memory_cost numeric(33, 2),
    infra_cost_model_volume_cost numeric(33, 2),
    sup_total_cost_model numeric(33, 2),
    sup_cost_model_cpu_cost numeric(33, 2),
    sup_cost_model_memory_cost numeric(33, 2),
    sup_cost_model_volume_cost numeric(33, 2)
);

-- loop construct
DO $BODY$
DECLARE
    schema_rec record;
    stmt_tmpl text = '
INSERT INTO __cust_openshift_cost_report (
    total_infrastructure_raw_cost,
    total_cost_model_costs,
    infra_total_cost_model,
    infra_cost_model_cpu_cost,
    infra_cost_model_memory_cost,
    infra_cost_model_volume_cost,
    sup_total_cost_model,
    sup_cost_model_cpu_cost,
    sup_cost_model_memory_cost,
    sup_cost_model_volume_cost
)

WITH infra_raw AS (
    SELECT
        ''%%1$s'' AS "customer",
        SUM(infrastructure_raw_cost) AS "infrastructure_raw_cost"
    FROM
        %%1$s.reporting_ocp_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
),
infra_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        SUM(cost_model_cpu_cost) AS "infra_cost_model_cpu_cost",
        SUM(cost_model_memory_cost) AS "infra_cost_model_memory_cost",
        SUM(cost_model_volume_cost) AS "infra_cost_model_volume_cost",
        SUM(cost_model_cpu_cost+cost_model_memory_cost+cost_model_volume_cost) AS "infra_total_cost_model"
    FROM
        %%1$s.reporting_ocp_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
        AND cost_model_rate_type=''Infrastructure''
),
sup_costs AS (
    SELECT
        ''%%1$s'' AS "customer",
        SUM(cost_model_cpu_cost) AS "sup_cost_model_cpu_cost",
        SUM(cost_model_memory_cost) AS "sup_cost_model_memory_cost",
        SUM(cost_model_volume_cost) AS "sup_cost_model_volume_cost",
        SUM(cost_model_cpu_cost+cost_model_memory_cost+cost_model_volume_cost) AS "sup_total_cost_model"
    FROM
        %%1$s.reporting_ocp_cost_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
        AND cost_model_rate_type=''Supplementary''
)
SELECT
        -- awc.customer AS "customer", -- customer is used for grouping, but left off report for anonymity
        COALESCE(ir.infrastructure_raw_cost, 0) AS "total_infrastructure_raw_cost",
        ic.infra_total_cost_model+sc.sup_total_cost_model AS "total_cost_model_costs",
        ic.infra_total_cost_model AS "infra_total_cost_model",
        ic.infra_cost_model_cpu_cost AS "infra_cost_model_cpu_cost",
        ic.infra_cost_model_memory_cost AS "infra_cost_model_memory_cost",
        ic.infra_cost_model_volume_cost AS "infra_cost_model_volume_cost",
        sc.sup_total_cost_model AS "sup_total_cost_model",
        sc.sup_cost_model_cpu_cost AS "sup_cost_model_cpu_cost",
        sc.sup_cost_model_memory_cost AS "sup_cost_model_memory_cost",
        sc.sup_cost_model_volume_cost AS "sup_cost_model_volume_cost"
    FROM
        infra_raw ir
        JOIN infra_costs ic ON ir.customer = ic.customer
        JOIN sup_costs sc ON ir.customer = sc.customer
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
