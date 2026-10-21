WITH schema_rows (customer, provider_id, cluster_id, node, report_month, cpu_cores, memory_gigabytes) AS (
SELECT :customer AS "customer",
       rpp.provider_id AS "provider_id",
       rpp.cluster_id AS "cluster_id",
       ro.node as "node",
       date_trunc('month', rpp.report_period_start)::date AS "report_month",
       max(ro.node_capacity_cpu_cores) AS "cpu_cores",
       max(ro.node_capacity_memory_gigabytes) AS "memory_gigabytes"
FROM   {schema}.reporting_ocpusagelineitem_daily_summary ro
JOIN   {schema}.reporting_ocpusagereportperiod rpp
ON     rpp.id = ro.report_period_id
WHERE ro.usage_start < :end_time
AND ro.usage_start >= :start_time
GROUP
   BY "customer",
      "provider_id",
      rpp.cluster_id,
      "node",
      "report_month"
)
SELECT
    CAST(customer AS text) AS customer,
    CAST(provider_id AS text) AS provider_id,
    CAST(cluster_id AS text) AS cluster_id,
    CAST(node AS text) AS node,
    CAST(report_month AS date) AS report_month,
    CAST(cpu_cores AS bigint) AS cpu_cores,
    CAST(memory_gigabytes AS bigint) AS memory_gigabytes
FROM schema_rows;
