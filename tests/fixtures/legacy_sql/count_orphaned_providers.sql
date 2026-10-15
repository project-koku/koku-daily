SELECT count (DISTINCT t.*),
       COALESCE(cust.account_id, 'unknown') as account_id,
       t.type as source_type,
       cust.org_id
FROM   public.api_provider t
       left join public.api_sources AS sources
              ON t.uuid :: text = sources.koku_uuid
       join public.api_customer AS cust
         ON t.customer_id = cust.id
WHERE  sources.koku_uuid IS NULL
GROUP BY cust.account_id, cust.org_id, t.type
