SELECT count (*) as "count",
       rm.assembly_id,
       rm.operator_certified,
       rm.operator_version,
       rm.cluster_id,
       c.account_id,
       p.type as source_type
  FROM public.reporting_common_costusagereportmanifest AS rm
  JOIN public.api_provider AS p
    ON p.uuid = rm.provider_id
  JOIN public.api_customer AS c
    ON c.id = p.customer_id
 WHERE (rm.operator_certified = true)
 GROUP
    BY c.account_id,
       rm.assembly_id,
       rm.operator_certified,
       rm.operator_version,
       rm.cluster_id,
       source_type
;