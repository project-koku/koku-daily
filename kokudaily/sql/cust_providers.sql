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
),
cost_report_manifest AS (
    SELECT provider_id,
           row_number() OVER (PARTITION BY provider_id ORDER BY manifest_creation_datetime DESC) AS row_number,
           assembly_id,
           operator_airgapped,
           operator_version,
           cluster_id,
           manifest_completed_datetime
    FROM   public.reporting_common_costusagereportmanifest
)
SELECT    fc.account_id,
          fc.org_id,
          p.uuid,
          p.type,
          CASE WHEN crm.manifest_completed_datetime >= now() - interval '48 HOURS'
              THEN true
              ELSE false
          END AS is_active,
          p.setup_complete,
          p.created_timestamp,
          p.data_updated_timestamp,
          crm.assembly_id,
          crm.cluster_id,
          crm.operator_airgapped,
          crm.operator_version
FROM      public.api_provider p
LEFT JOIN public.api_sources AS sources
ON        p.uuid :: text = sources.koku_uuid
JOIN      filtered_customers AS fc
ON        p.customer_id = fc.id
LEFT JOIN cost_report_manifest AS crm
ON        p.uuid = crm.provider_id
WHERE     sources.koku_uuid IS NOT NULL
AND       coalesce(crm.row_number, 1) = 1
ORDER BY  p.uuid,
          fc.account_id,
	      fc.org_id
