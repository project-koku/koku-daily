SELECT    c.id as customer_id,
          c.schema_name,
          p.uuid as provider_uuid,
          p.type as source_type,
          rm.assembly_id,
          rm.manifest_creation_datetime,
          rm.manifest_updated_datetime,
          rm.billing_period_start_datetime,
          rm.num_processed_files,
          rm.num_total_files,
          rs.report_name,
          rs.last_started_datetime as report_start_datetime,
          rs.last_completed_datetime as report_completed_datetime
FROM      public.reporting_common_costusagereportmanifest AS rm
JOIN      public.api_provider AS p
ON        rm.provider_id = p.uuid
JOIN      public.api_customer AS c
ON        p.customer_id = c.id
LEFT JOIN public.reporting_common_costusagereportstatus AS rs
ON        rm.id = rs.manifest_id
WHERE     num_processed_files != num_total_files
AND       manifest_creation_datetime >= current_date - INTERVAL '1 day'
ORDER BY  c.id,
          p.type,
          rm.manifest_creation_datetime
;
