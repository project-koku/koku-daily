WITH cust_non_redhat AS (
    SELECT DISTINCT t.customer_id,
                    substring(t.email from '@(.*)$') AS domain
    FROM            PUBLIC.api_user t
    WHERE           substring(t.email FROM '@(.*)$') != 'redhat.com'
)
SELECT c.account_id,
       cnr.domain,
       p.name,
       p.type,
       p.setup_complete
FROM   PUBLIC.api_customer c
JOIN   cust_non_redhat AS cnr
ON     cnr.customer_id = c.id
JOIN   PUBLIC.api_provider AS p
ON     p.customer_id = c.id
WHERE  c.account_id NOT IN ('6089719',
                            '1460290',
                            '5910538',
                            '540155',
                            '6289400',
                            '6289401')
AND    date(p.created_timestamp) <= date(now() - INTERVAL '6 days')
