 WITH cust_non_redhat AS (
    SELECT t.customer_id,
           array_agg(DISTINCT substring(t.email from '@(.*)$')) AS domain
    FROM   PUBLIC.api_user t
    WHERE  substring(t.email FROM '@(.*)$') != 'redhat.com'
    GROUP BY t.customer_id
),
filtered_customers AS (
    SELECT   c.id,
             COALESCE(c.account_id, 'unknown') as account_id,
             cnr.domain,
             c.org_id
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
SELECT sum(configured) as count_configured,
       sum(mixed) as count_mixed,
       sum(unconfigured) as count_unconfigured
FROM (
    SELECT c.account_id,
           c.org_id,
           c.domain,
           CASE WHEN c.count_unconfigured > 0 AND c.count_configured > 0
               THEN 1
               ELSE 0
               END as mixed,
           CASE WHEN c.count_unconfigured > 0 AND c.count_configured = 0
               THEN 1
               ELSE 0
               END as unconfigured,
           CASE WHEN c.count_unconfigured = 0 AND c.count_configured > 0
               THEN 1
               ELSE 0
               END as configured
    FROM (
        SELECT   fc.account_id,
                 fc.org_id,
                 fc.domain,
                 count(p.uuid) FILTER (WHERE p.setup_complete = FALSE) as count_unconfigured,
                 count(p.uuid) FILTER (WHERE p.setup_complete = TRUE) as count_configured
        FROM     PUBLIC.api_provider p
        JOIN     filtered_customers AS fc
        ON       p.customer_id = fc.id
        GROUP BY fc.account_id,
                 fc.org_id,
                 fc.domain
    ) AS c
) as s
