 SELECT t.*,
       cust.account_id
FROM   PUBLIC.api_provider t
JOIN   PUBLIC.api_providerstatus AS status
ON     t.uuid = status.provider_id
JOIN   PUBLIC.api_customer AS cust
ON     t.customer_id = cust.id
WHERE  status.timestamp <= Now() - interval '48 HOURS'
