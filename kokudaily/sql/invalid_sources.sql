SELECT t.*
FROM   PUBLIC.api_sources t
WHERE  ( t.koku_uuid IS NULL
          OR t.koku_uuid = '' )
        OR ( t.account_id IS NULL
              OR t.account_id = '' )
        OR ( t.source_type IS NULL
              OR t.source_type = '' )
