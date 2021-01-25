 WITH cust_non_redhat AS (
    SELECT t.customer_id,
           array_agg(DISTINCT substring(t.email from '@(.*)$')) AS domain
    FROM   PUBLIC.api_user t
    WHERE  substring(t.email FROM '@(.*)$') != 'redhat.com'
    GROUP BY t.customer_id
),
filtered_customers AS (
         SELECT   c.id,
                  c.account_id,
                  cnr.domain
         FROM     PUBLIC.api_customer c
         JOIN     cust_non_redhat AS cnr
         ON       cnr.customer_id = c.id
         WHERE    c.account_id NOT IN ('6089719',
                                       '1460290',
                                       '5910538',
                                       '540155',
                                       '6289400',
                                       '6289401')
         GROUP BY c.id,
                  cnr.domain )
SELECT   count (DISTINCT t.uuid),
         fc.account_id,
         fc.domain,
         t.type,
         t.setup_complete
FROM     PUBLIC.api_provider t
JOIN     filtered_customers AS fc
ON       t.customer_id = fc.id
GROUP BY fc.account_id,
         fc.domain,
         t.type,
         t.setup_complete
