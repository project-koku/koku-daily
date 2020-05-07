SELECT count (DISTINCT cust.*)
FROM   PUBLIC.api_customer AS cust
       LEFT JOIN PUBLIC.api_provider p
              ON cust.id = p.customer_id
       JOIN PUBLIC.api_tenant t
         ON cust.schema_name = t.schema_name
WHERE  p.customer_id IS NULL
