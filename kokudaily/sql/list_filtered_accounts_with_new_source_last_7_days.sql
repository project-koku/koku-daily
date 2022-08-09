WITH cust_non_redhat AS (
    SELECT t.customer_id,
           array_agg(DISTINCT substring(t.email from '@(.*)$')) AS domain
    FROM   PUBLIC.api_user t
    WHERE  substring(t.email FROM '@(.*)$') != 'redhat.com'
    GROUP BY t.customer_id
)
SELECT COALESCE(c.account_id, 'unknown') as account_id,
       c.org_id,
       cnr.domain,
       p.name,
       p.type,
       p.setup_complete
FROM   PUBLIC.api_customer c
JOIN   cust_non_redhat AS cnr
ON     cnr.customer_id = c.id
JOIN   PUBLIC.api_provider AS p
ON     p.customer_id = c.id
WHERE    c.org_id NOT IN ('11789772',
                          '6340056',
                          '11009103',
                          '1979710',
                          '12667745',
                          '12667749')
AND    date(p.created_timestamp) >= date(now() - INTERVAL '6 days')
ORDER BY p.type, p.setup_complete
