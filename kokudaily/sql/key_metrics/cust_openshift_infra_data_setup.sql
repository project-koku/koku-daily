DROP TABLE IF EXISTS __cust_openshift_infra_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_openshift_infra_report (
    id serial,
    month date,
    cluster_count integer,
    node_count integer,
    pvc_count integer,
    cluster_capacity_cores numeric(33, 2),
    cluster_capacity_core_hours numeric(33, 2),
    cluster_capacity_memory_gb numeric(33, 2),
    cluster_capacity_memory_gb_hours numeric(33, 2),
    volume_request_gb numeric(33, 2),
    volume_request_gb_mo numeric(33, 2),
    pvc_capacity_gb numeric(33, 2),
    pvc_capacity_gb_mo numeric(33, 2)
);

-- loop construct
DO $BODY$
DECLARE
    schema_rec record;
    stmt_tmpl text = '
INSERT INTO __cust_openshift_infra_report (
    month,
    cluster_count,
    node_count,
    pvc_count,
    cluster_capacity_cores,
    cluster_capacity_core_hours,
    cluster_capacity_memory_gb,
    cluster_capacity_memory_gb_hours,
    volume_request_gb,
    volume_request_gb_mo,
    pvc_capacity_gb,
    pvc_capacity_gb_mo
)
WITH compute AS (
    SELECT
        ''%%1$s'' AS "customer",
        DATE_TRUNC(''month'', usage_start) AS "month",
        cluster_id,
        count(distinct node) AS nodes,
        max(cluster_capacity_cpu_core_hours)/24 AS "clus_cap_cores",
        max(cluster_capacity_cpu_core_hours) AS "clus_cap_core_hours",
        max(cluster_capacity_memory_gigabyte_hours)/24 AS "clus_cap_mem",
        max(cluster_capacity_memory_gigabyte_hours) AS "clus_cap_mem_hours"
    FROM
        %%1$s.reporting_ocp_pod_summary_by_node_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
        AND cost_model_rate_type IS NULL
    GROUP BY
        cluster_id,
        month
),
compute_agg AS (
    SELECT
        ''%%1$s'' AS "customer",
        month AS "month",
        count(distinct cluster_id) AS cluster_count,
        sum(nodes) AS node_count,
        sum(clus_cap_cores) AS cluster_capacity_cores,
        sum(clus_cap_core_hours) AS cluster_capacity_core_hours,
        sum(clus_cap_mem) AS cluster_capacity_memory_gb,
        sum(clus_cap_mem_hours) AS cluster_capacity_memory_gb_hours
    FROM compute
    GROUP BY month
),
storage AS (
    SELECT
        ''%%1$s'' AS "customer",
        DATE_TRUNC(''month'', usage_start) AS "month",
        cluster_id,
        persistentvolumeclaim,
        max(volume_request_storage_gigabyte_months) * extract(days FROM date_trunc(''month'', usage_start) + ''1 month - 1 day''::interval) AS "vol_req_gb",
        sum(volume_request_storage_gigabyte_months) as "vol_req_gb_mo",
        max(persistentvolumeclaim_capacity_gigabyte_months) * extract(days FROM date_trunc(''month'', usage_start) + ''1 month - 1 day''::interval) AS "pvc_cap_gb",
        sum(persistentvolumeclaim_capacity_gigabyte_months) AS "pvc_cap_gb_mo"
    FROM
        %%1$s.reporting_ocp_volume_summary_p
    WHERE
        usage_start >= ''%%2$s''::date
        AND usage_start < ''%%3$s''::date
        AND cost_model_rate_type IS NULL
    GROUP BY
        cluster_id,
        persistentvolumeclaim,
        month
),
storage_agg AS (
    SELECT
        ''%%1$s'' AS "customer",
        month AS "month",
        count(persistentvolumeclaim) AS "pvc_count",
        sum(vol_req_gb) AS "volume_request_gb",
        sum(vol_req_gb_mo) AS "volume_request_gb_mo",
        sum(pvc_cap_gb) AS "pvc_capacity_gb",
        sum(pvc_cap_gb_mo) AS "pvc_capacity_gb_mo"
    FROM storage
    GROUP BY month
)
SELECT
    -- customer is used for grouping, but left off report for anonymity
    month,
    cluster_count,
    node_count,
    pvc_count,
    cluster_capacity_cores,
    cluster_capacity_core_hours,
    cluster_capacity_memory_gb,
    cluster_capacity_memory_gb_hours,
    volume_request_gb,
    volume_request_gb_mo,
    pvc_capacity_gb,
    pvc_capacity_gb_mo
FROM compute_agg c
FULL OUTER JOIN storage_agg s USING (customer, month)
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
