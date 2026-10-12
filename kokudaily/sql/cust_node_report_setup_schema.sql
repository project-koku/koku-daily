INSERT
  INTO __cust_node_report (
      customer,
      provider_id,
      cluster_id,
      node,
      report_month,
      cpu_cores,
      memory_gigabytes
  )
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
      "report_month";
