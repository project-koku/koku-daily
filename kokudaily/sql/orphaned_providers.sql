SELECT cust.account_id,
       t.*
FROM   public.api_provider t
       join public.api_sources AS sources
         ON t.uuid :: text != sources.koku_uuid
       join public.api_customer AS cust
         ON t.customer_id = cust.id
GROUP  BY t.uuid,
          cust.account_id  