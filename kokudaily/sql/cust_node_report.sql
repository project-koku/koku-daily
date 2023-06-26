-- Get customer node information based on the data from the _setup.sql
WITH cust_non_redhat AS (
    SELECT u.customer_id,
           array_agg(DISTINCT substring(u.email FROM '@(.*)$')) AS domain
    FROM   public.api_user u
    WHERE  substring(u.email FROM '@(.*)$') != 'redhat.com'
    GROUP
       BY  u.customer_id
),
filtered_customers AS (
    SELECT c.id,
           coalesce(c.account_id, 'unknown') AS account_id,
           c.org_id,
           c.schema_name,
           cnr.domain
    FROM   public.api_customer c
    JOIN   cust_non_redhat AS cnr
    ON     cnr.customer_id = c.id
    WHERE  c.org_id NOT IN ('11789772',
                            '6340056',
                            '11009103',
                            '1979710',
                            '12667745',
                            '12667749')
    GROUP
       BY  c.id,
           cnr.domain
)
SELECT fc.account_id,
       cnr.provider_id,
       cnr.cluster_id,
       cnr.node,
       cnr.report_month,
       cnr.cpu_cores,
       cnr.memory_bytes,
       fc.org_id
  FROM __cust_node_report cnr
  JOIN filtered_customers AS fc
    ON cnr.customer = fc.schema_name
