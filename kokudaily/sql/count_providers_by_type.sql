 WITH cust_non_redhat AS (
    SELECT DISTINCT t.customer_id,
                    substring(t.email from '@(.*)$') AS domain
    FROM            PUBLIC.api_user t
    WHERE           substring(t.email FROM '@(.*)$') != 'redhat.com'
),
filtered_customers AS (
    SELECT   c.id,
             c.org_id,
             cnr.domain
    FROM     PUBLIC.api_customer c
    JOIN     cust_non_redhat AS cnr
    ON       cnr.customer_id = c.id
    WHERE    c.org_id NOT IN ('11789772',
                              '6340056',
                              '11009103',
                              '1979710',
                              '12667745',
                              '12667749')
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
