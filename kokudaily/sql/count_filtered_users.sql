 WITH cust_non_redhat AS
(
                SELECT DISTINCT t.customer_id,
                                substring(t.email from '@(.*)$') AS domain
                FROM            PUBLIC.api_user t
                WHERE           substring(t.email FROM '@(.*)$') != 'redhat.com' ),
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
),
cte_active_customers AS (
    SELECT DISTINCT customer_id
    FROM PUBLIC.api_provider
)
SELECT count(DISTINCT t.username) FILTER (WHERE ac.customer_id IS NOT NULL)
FROM   PUBLIC.api_user t
JOIN   filtered_customers AS fc
ON     t.customer_id = fc.id
LEFT JOIN cte_active_customers AS ac
ON     t.customer_id = ac.customer_id
