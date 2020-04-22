SELECT cust.account_id,
       t.*
FROM   PUBLIC.api_provider t
       LEFT JOIN PUBLIC.api_sources AS sources
              ON sources.koku_uuid IS NULL
       JOIN PUBLIC.api_customer AS cust
         ON t.customer_id = cust.id
GROUP  BY t.uuid,
          cust.account_id  