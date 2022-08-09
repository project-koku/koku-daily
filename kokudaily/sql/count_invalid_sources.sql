SELECT count (DISTINCT t.source_id),
       COALESCE(t.account_id, 'unknown') as account_id,
       COALESCE(t.org_id, 'unknown') as org_id,
       COALESCE(NULLIF(t.source_type, ''), 'unknown') as source_type
FROM   PUBLIC.api_sources t
WHERE  ( t.koku_uuid IS NULL
          OR t.koku_uuid = '' )
        OR ( t.org_id IS NULL
              OR t.org_id = '' )
        OR ( t.source_type IS NULL
              OR t.source_type = '' )
GROUP BY t.account_id, t.org_id, t.source_type
