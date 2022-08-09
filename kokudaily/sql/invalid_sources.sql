SELECT COALESCE(t.account_id, 'unknown') as account_id,
       t.org_id,
       t.source_id,
       t.name,
       t.source_uuid,
       t.koku_uuid,
       t.source_type,
       t.status
FROM   PUBLIC.api_sources t
WHERE  ( t.koku_uuid IS NULL
          OR t.koku_uuid = '' )
        OR ( t.org_id IS NULL
              OR t.org_id = '' )
        OR ( t.source_type IS NULL
              OR t.source_type = '' )
