DROP TABLE IF EXISTS __cust_node_report;
-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_node_report (
    customer text,
    provider_id text,
    cluster_id text,
    node text,
    report_month date,
    pod_count bigint,
    cpu_cores bigint,
    memory_bytes bigint
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
      pod_count,
      cpu_cores,
      memory_bytes
  )
SELECT ''%%1$s'' AS "customer",
       rpp.provider_id AS "provider_id",
       rpp.cluster_id AS "cluster_id",
       ro.node as "node",
       date_trunc(''month'', rp.interval_start)::date AS "report_month",
       count(DISTINCT ro.pod) AS "pod_count",
       max(ro.node_capacity_cpu_cores) AS "cpu_cores",
       max(ro.node_capacity_memory_bytes) AS "memory_bytes"
       -- starting with line item as we need the data ingestion counts
FROM   %%1$s.reporting_ocpusagelineitem ro
       -- usage report has the usage bounds
JOIN   %%1$s.reporting_ocpusagereport rp
ON     rp.id = ro.report_id
AND    rp.interval_start < ''%%3$s''::timestamptz  -- start must be < end bounds as end bounds is start of next month
AND    rp.interval_end >= ''%%2$s''::timestamptz   -- end must be >= start bounds
       -- report period has the provider and cluster
JOIN   %%1$s.reporting_ocpusagereportperiod rpp
ON     rpp.id = ro.report_period_id
GROUP
   BY "customer",
      "provider_id",
      "cluster_id",
      "node",
      "report_month";
';
BEGIN
    FOR schema_rec IN
        SELECT t.schema_name
        FROM   public.api_tenant t
        JOIN   pg_namespace n
        ON     n.nspname = t.schema_name
        JOIN   public.api_customer c
        ON     c.schema_name = t.schema_name
        JOIN   public.api_provider p
        ON     p.customer_id = c.id
        AND    p.type = any( %(provider_types)s )
        WHERE  t.schema_name ~ '^acct'
        OR     t.schema_name ~ '^org'
        ORDER
        BY     t.schema_name
    LOOP
        EXECUTE format(stmt_tmpl, schema_rec.schema_name, %(start_time)s, %(end_time)s);
    END LOOP;
END $BODY$ LANGUAGE plpgsql;
