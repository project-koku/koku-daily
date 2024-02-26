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
SELECT    COALESCE(cust.account_id, 'unknown') as account_id,
          t.*,
          auth.credentials->>'cluster_id' as cluster_id,
          cust.org_id
FROM      PUBLIC.api_provider t
LEFT JOIN PUBLIC.api_sources AS sources
ON        t.uuid :: text = sources.koku_uuid
JOIN      PUBLIC.api_providerauthentication AS auth
ON        t.authentication_id  = auth.id
JOIN      cte_manifest_temp AS status
ON        t.uuid = status.provider_id
JOIN      PUBLIC.api_customer AS cust
ON        t.customer_id = cust.id
WHERE     status.completed_datetime >= now() - interval '48 HOURS'
AND       sources.koku_uuid IS NOT NULL
;
