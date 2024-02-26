SELECT    c.id as customer_id,
          c.schema_name,
          p.uuid as provider_uuid,
          p.type as source_type,
          rm.assembly_id,
          rm.creation_datetime,
          counts.updated_datetime,
          rm.completed_datetime,
          rm.billing_period_start_datetime,
          counts.num_processed_files,
          counts.num_total_files
FROM      public.reporting_common_costusagereportmanifest AS rm
JOIN      public.api_provider AS p
ON        rm.provider_id = p.uuid
JOIN      public.api_customer AS c
ON        p.customer_id = c.id
JOIN (
    SELECT   rm.id,
             count(rs.*) FILTER (WHERE rs.completed_datetime IS NOT NULL) AS num_processed_files,
             count(rs.*) AS num_total_files,
             max(rs.completed_datetime) as updated_datetime
    FROM     public.reporting_common_costusagereportmanifest AS rm
    JOIN     public.reporting_common_costusagereportstatus AS rs
    ON       rm.id = rs.manifest_id
    GROUP BY rm.id
) AS counts
ON        rm.id = counts.id
WHERE     counts.num_processed_files != counts.num_total_files
AND       rm.creation_datetime >= current_date - INTERVAL '1 day'
AND       counts.updated_datetime < now() - INTERVAL '10 min' -- It has been longer than 10 minutes since we processed anything
ORDER BY  c.id,
          p.type,
          rm.creation_datetime
;
