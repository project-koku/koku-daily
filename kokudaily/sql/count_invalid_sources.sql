SELECT count (DISTINCT t.source_id),
       COALESCE(t.account_id, 'unknown') as account_id,
       COALESCE(NULLIF(t.source_type, ''), 'unknown') as source_type
FROM   PUBLIC.api_sources t
WHERE  ( t.koku_uuid IS NULL
          OR t.koku_uuid = '' )
        OR ( t.account_id IS NULL
              OR t.account_id = '' )
        OR ( t.source_type IS NULL
              OR t.source_type = '' )
GROUP BY t.account_id, t.source_type
