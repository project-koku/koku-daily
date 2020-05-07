SELECT    count (DISTINCT rm.*),
          REPLACE(c.schema_name, 'acct', '') as account_id,
          p.type as source_type
FROM      public.reporting_common_costusagereportmanifest AS rm
JOIN      public.api_provider AS p
ON        rm.provider_id = p.uuid
JOIN      public.api_customer AS c
ON        p.customer_id = c.id
WHERE     num_processed_files != num_total_files
AND       manifest_creation_datetime >= current_date - INTERVAL '1 day'
GROUP BY c.schema_name, p.type
;
