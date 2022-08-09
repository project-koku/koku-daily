WITH cust_non_redhat AS (
    SELECT t.customer_id,
           array_agg(DISTINCT substring(t.email from '@(.*)$')) AS domain
    FROM   PUBLIC.api_user t
    WHERE  substring(t.email FROM '@(.*)$') != 'redhat.com'
    GROUP BY t.customer_id
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
SELECT   count (DISTINCT t.uuid),
         fc.org_id,
         fc.domain
FROM     PUBLIC.api_provider t
JOIN     filtered_customers AS fc
ON       t.customer_id = fc.id
GROUP BY fc.org_id,
         fc.domain
