 WITH cust_redhat AS (
    SELECT DISTINCT t.customer_id,
                    substring(t.email from '@(.*)$') AS domain
    FROM            PUBLIC.api_user t
    WHERE           substring(t.email FROM '@(.*)$') = 'redhat.com'
),
filtered_customers AS (
    SELECT   c.id,
             COALESCE(c.account_id, 'unknown') as account_id,
             cnr.domain,
             c.org_id
    FROM     PUBLIC.api_customer c
    JOIN     cust_redhat AS cnr
    ON       cnr.customer_id = c.id
    GROUP BY c.id,
            cnr.domain
)
SELECT   p.type,
         p.setup_complete,
         count (DISTINCT p.uuid) as count
FROM     PUBLIC.api_provider AS p
JOIN     filtered_customers AS fc
ON       p.customer_id = fc.id
GROUP BY p.type, p.setup_complete
ORDER BY p.type, p.setup_complete
