SELECT    cust.account_id,
          t.*
FROM      PUBLIC.api_provider t
LEFT JOIN PUBLIC.api_sources AS sources
ON        t.uuid :: text = sources.koku_uuid
JOIN      PUBLIC.api_providerstatus AS status
ON        t.uuid = status.provider_id
JOIN      PUBLIC.api_customer AS cust
ON        t.customer_id = cust.id
WHERE     status.timestamp >= now() - interval '48 HOURS'
AND       sources.koku_uuid IS NOT NULL
