SELECT t.account_id,
       t.source_id,
       t.name,
       t.source_uuid,
       t.koku_uuid,
       t.source_type,
       t.status
FROM   PUBLIC.api_sources t
WHERE  ( t.koku_uuid IS NULL
          OR t.koku_uuid = '' )
        OR ( t.account_id IS NULL
              OR t.account_id = '' )
        OR ( t.source_type IS NULL
              OR t.source_type = '' )
