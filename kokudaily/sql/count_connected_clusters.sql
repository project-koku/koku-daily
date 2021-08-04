SELECT    count (DISTINCT rm.*) filter (WHERE operator_airgapped = false),
          REPLACE(c.schema_name, 'acct', '') as account_id,
          p.type as source_type
FROM      public.reporting_common_costusagereportmanifest AS rm
JOIN      public.api_provider AS p
ON        rm.provider_id = p.uuid
JOIN      public.api_customer AS c
ON        p.customer_id = c.id
GROUP BY  c.schema_name,
          p.type,
          rm.operator_airgapped,
          rm.provider_id
;
