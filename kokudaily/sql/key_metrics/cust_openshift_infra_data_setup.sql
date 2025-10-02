DROP TABLE IF EXISTS __cust_openshift_infra_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_openshift_infra_report (
    schema text,
    date date,
    cluster_count integer,
    node_count integer,
    architecture text,
    infra_node_count integer,
    control_plane_node_count integer,
    worker_node_count integer,
    infra_node_cpu_cores numeric(33, 2),
    control_plane_node_cpu_cores numeric(33, 2),
    worker_node_cpu_cores numeric(33, 2),
    infra_node_mem_gb numeric(33, 2),
    control_plane_node_mem_gb numeric(33, 2),
    worker_node_mem_gb numeric(33, 2),
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
    schema,
    date,
    cluster_count,
    node_count,
    architecture,
    infra_node_count,
    control_plane_node_count,
    worker_node_count,
    infra_node_cpu_cores,
    control_plane_node_cpu_cores,
    worker_node_cpu_cores,
    infra_node_mem_gb,
    control_plane_node_mem_gb,
    worker_node_mem_gb,
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
WITH schemas AS (
    SELECT
        ''%1$s'' AS "customer",
        generate_series(date_trunc(''month'', ''%2$s''::date), now(), ''1 day'')::date AS "date"
),
node_info as (
    SELECT
        ron.node AS node,
        ron.node_role AS node_role,
        ron.architecture AS architecture,
        max(ropsbn.node_capacity_cpu_cores) AS node_capacity_cpu_cores,
        max(ropsbn.node_capacity_memory_gigabytes) AS node_capacity_memory_gigabytes,
        usage_start
    FROM %1$s.reporting_ocp_pod_summary_by_node_p ropsbn
    LEFT JOIN %1$s.reporting_ocp_nodes ron USING (node)
    WHERE
        usage_start >= ''%2$s''::date
        AND usage_start < ''%3$s''::date
    GROUP BY ron.node, ron.node_role, ron.architecture, usage_start
    ORDER BY node_role, usage_start
),
node_agg as(
    SELECT
        node_role,
        architecture,
        count(node_role) as role_count,
        sum(node_capacity_cpu_cores) as node_cpu_cores,
        sum(node_capacity_memory_gigabytes) as node_mem_gb,
        usage_start
    FROM node_info
    GROUP BY node_role, architecture, usage_start
),
node_counts AS (
    SELECT
        ''%1$s'' AS "customer",
        architecture,
        SUM(CASE WHEN node_role = ''infra'' THEN role_count END) as "infra_node_count",
        SUM(CASE WHEN node_role IN (''master'', ''control-plane'') THEN role_count END) as "control_plane_node_count",
        SUM(CASE WHEN node_role = ''worker'' THEN role_count END) as "worker_node_count",
        SUM(CASE WHEN node_role = ''infra'' THEN node_cpu_cores END) as "infra_node_cpu_cores",
        SUM(CASE WHEN node_role IN (''master'', ''control-plane'') THEN node_cpu_cores END) as "control_plane_node_cpu_cores",
        SUM(CASE WHEN node_role = ''worker'' THEN node_cpu_cores END) as "worker_node_cpu_cores",
        SUM(CASE WHEN node_role = ''infra'' THEN node_mem_gb END) as "infra_node_mem_gb",
        SUM(CASE WHEN node_role IN (''master'', ''control-plane'') THEN node_mem_gb END) as "control_plane_node_mem_gb",
        SUM(CASE WHEN node_role = ''worker'' THEN node_mem_gb END) as "worker_node_mem_gb",
        usage_start AS "date"
    FROM node_agg GROUP BY architecture, usage_start
),
compute AS (
    SELECT
        ''%1$s'' AS "customer",
        usage_start AS "date",
        ropsbn.cluster_id,
        count(distinct node) AS nodes,
        ron.architecture,
        max(cluster_capacity_cpu_core_hours)/24 AS "clus_cap_cores",
        max(cluster_capacity_cpu_core_hours) AS "clus_cap_core_hours",
        max(cluster_capacity_memory_gigabyte_hours)/24 AS "clus_cap_mem",
        max(cluster_capacity_memory_gigabyte_hours) AS "clus_cap_mem_hours"
    FROM
        %1$s.reporting_ocp_pod_summary_by_node_p ropsbn
    JOIN %1$s.reporting_ocp_nodes ron USING (node)
    WHERE
        usage_start >= ''%2$s''::date
        AND usage_start < ''%3$s''::date
        AND cost_model_rate_type IS NULL
    GROUP BY
        ropsbn.cluster_id,
        usage_start,
        architecture
),
compute_agg AS (
    SELECT
        ''%1$s'' AS "customer",
        date AS "date",
        count(distinct cluster_id) AS cluster_count,
        sum(nodes) AS node_count,
        architecture,
        sum(clus_cap_cores) AS cluster_capacity_cores,
        sum(clus_cap_core_hours) AS cluster_capacity_core_hours,
        sum(clus_cap_mem) AS cluster_capacity_memory_gb,
        sum(clus_cap_mem_hours) AS cluster_capacity_memory_gb_hours
    FROM compute
    GROUP BY date, architecture
),
node_compute_agg AS (
    SELECT
        *
    FROM node_counts
    JOIN compute_agg USING (customer, date, architecture)
),
storage AS (
    SELECT
        ''%1$s'' AS "customer",
        usage_start AS "date",
        cluster_id,
        persistentvolumeclaim,
        max(volume_request_storage_gigabyte_months) * extract(days FROM date_trunc(''month'', usage_start) + ''1 month - 1 day''::interval) AS "vol_req_gb",
        sum(volume_request_storage_gigabyte_months) as "vol_req_gb_mo",
        max(persistentvolumeclaim_capacity_gigabyte_months) * extract(days FROM date_trunc(''month'', usage_start) + ''1 month - 1 day''::interval) AS "pvc_cap_gb",
        sum(persistentvolumeclaim_capacity_gigabyte_months) AS "pvc_cap_gb_mo"
    FROM
        %1$s.reporting_ocp_volume_summary_p
    WHERE
        usage_start >= ''%2$s''::date
        AND usage_start < ''%3$s''::date
        AND cost_model_rate_type IS NULL
    GROUP BY
        cluster_id,
        persistentvolumeclaim,
        usage_start
),
storage_agg AS (
    SELECT
        ''%1$s'' AS "customer",
        date AS "date",
        count(persistentvolumeclaim) AS "pvc_count",
        sum(vol_req_gb) AS "volume_request_gb",
        sum(vol_req_gb_mo) AS "volume_request_gb_mo",
        sum(pvc_cap_gb) AS "pvc_capacity_gb",
        sum(pvc_cap_gb_mo) AS "pvc_capacity_gb_mo"
    FROM storage
    GROUP BY date
)
SELECT
    s.customer AS "schema",
    s.date,
    cluster_count,
    node_count,
    architecture,
    infra_node_count,
    control_plane_node_count,
    worker_node_count,
    infra_node_cpu_cores,
    control_plane_node_cpu_cores,
    worker_node_cpu_cores,
    infra_node_mem_gb,
    control_plane_node_mem_gb,
    worker_node_mem_gb,
    pvc_count,
    cluster_capacity_cores,
    cluster_capacity_core_hours,
    cluster_capacity_memory_gb,
    cluster_capacity_memory_gb_hours,
    volume_request_gb,
    volume_request_gb_mo,
    pvc_capacity_gb,
    pvc_capacity_gb_mo
FROM
schemas s
FULL OUTER JOIN node_compute_agg ca USING (customer, date)
FULL OUTER JOIN storage_agg sa USING (customer, date)
ORDER BY date
';
BEGIN
    FOR schema_rec IN SELECT DISTINCT
        t.schema_name
    FROM
        public.api_tenant t
        JOIN pg_namespace n ON n.nspname = t.schema_name
        JOIN public.api_customer c ON c.schema_name = t.schema_name
    WHERE
        t.schema_name NOT IN ('acct6193296', 'acct6089719')
        AND (t.schema_name ~ '^acct' OR t.schema_name ~ '^org')
    ORDER BY
        t.schema_name
    LOOP
        EXECUTE format(stmt_tmpl, schema_rec.schema_name, (:start_time), (:end_time));
    END LOOP;
END $BODY$ LANGUAGE plpgsql;
