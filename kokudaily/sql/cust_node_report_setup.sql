DROP TABLE IF EXISTS __cust_node_report;
-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_node_report (
    customer text,
    provider_id text,
    cluster_id text,
    node text,
    report_month date,
    cpu_cores bigint,
    memory_gigabytes bigint
);
CREATE INDEX ix__cust_node_report ON __cust_node_report (customer, provider_id, cluster_id, node, report_month);
-- loop construct
DO $BODY$
DECLARE
    schema_rec record;
    -- OCP data gather per-schema
    stmt_tmpl text = '
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
SELECT ''%1$s'' AS "customer",
       rpp.provider_id AS "provider_id",
       rpp.cluster_id AS "cluster_id",
       ro.node as "node",
       date_trunc(''month'', rpp.report_period_start)::date AS "report_month",
       max(ro.node_capacity_cpu_cores) AS "cpu_cores",
       max(ro.node_capacity_memory_gigabytes) AS "memory_gigabytes"
FROM   %1$s.reporting_ocpusagelineitem_daily_summary ro
JOIN   %1$s.reporting_ocpusagereportperiod rpp
ON     rpp.id = ro.report_period_id
WHERE ro.usage_start < ''%3$s''::timestamptz
AND ro.usage_start >= ''%2$s''::timestamptz
GROUP
   BY "customer",
      "provider_id",
      rpp.cluster_id,
      "node",
      "report_month";
';
BEGIN
    FOR schema_rec IN
        SELECT DISTINCT t.schema_name
        FROM   public.api_tenant t
        JOIN   pg_namespace n
        ON     n.nspname = t.schema_name
        JOIN   public.api_customer c
        ON     c.schema_name = t.schema_name
        JOIN   public.api_provider p
        ON     p.customer_id = c.id
        AND    p.type = any( (:provider_types) )
        WHERE  t.schema_name ~ '^acct'
        OR     t.schema_name ~ '^org'
        ORDER
        BY     t.schema_name
    LOOP
        EXECUTE format(stmt_tmpl, schema_rec.schema_name, (:start_time), (:end_time));
    END LOOP;
END $BODY$ LANGUAGE plpgsql;
