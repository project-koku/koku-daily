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
                  cnr.domain )
SELECT   count (DISTINCT t.uuid),
         fc.account_id,
         fc.org_id,
         fc.domain,
         t.type,
         t.setup_complete,
         count (DISTINCT t.uuid) FILTER (WHERE t.type = 'OCP' AND t.setup_complete = TRUE) as ocp_setup_complete_count,
         count (DISTINCT t.uuid) FILTER (WHERE t.type = 'AWS' AND t.setup_complete = TRUE) as aws_setup_complete_count,
         count (DISTINCT t.uuid) FILTER (WHERE t.type = 'Azure' AND t.setup_complete = TRUE) as azure_setup_complete_count,
         count (DISTINCT t.uuid) FILTER (WHERE t.type = 'GCP' AND t.setup_complete = TRUE) as gcp_setup_complete_count
FROM     PUBLIC.api_provider t
JOIN     filtered_customers AS fc
ON       t.customer_id = fc.id
GROUP BY fc.account_id,
         fc.org_id,
         fc.domain,
         t.type,
         t.setup_complete
