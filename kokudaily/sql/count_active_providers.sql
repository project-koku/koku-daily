WITH cte_manifest_temp AS (
    SELECT  DISTINCT ON(provider_id)
            provider_id,
            id,
            completed_datetime
    FROM PUBLIC.reporting_common_costusagereportmanifest
    ORDER BY provider_id,
             id
    DESC NULLS LAST
)
SELECT    DISTINCT ON(status.provider_id)
          count (DISTINCT t.*),
          COALESCE(cust.account_id, 'unknown') as account_id,
          t.type as source_type,
          cust.org_id
FROM      PUBLIC.api_provider t
LEFT JOIN PUBLIC.api_sources AS sources
ON        t.uuid :: text = sources.koku_uuid
JOIN      cte_manifest_temp AS status
ON        t.uuid = status.provider_id
JOIN      PUBLIC.api_customer AS cust
ON        t.customer_id = cust.id
WHERE     status.completed_datetime >= now() - interval '48 HOURS'
AND       sources.koku_uuid IS NOT NULL
GROUP BY cust.account_id, cust.org_id, t.type, status.provider_id
;
