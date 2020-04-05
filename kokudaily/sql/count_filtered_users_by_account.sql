 WITH cust_non_redhat AS
(
                SELECT DISTINCT t.customer_id,
                                substring(t.email from '@(.*)$') AS domain
                FROM            PUBLIC.api_user t
                WHERE           substring(t.email FROM '@(.*)$') != 'redhat.com' ), filtered_customers AS
(
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
SELECT   count (DISTINCT t.username),
         fc.domain
FROM     PUBLIC.api_user t
JOIN     filtered_customers AS fc
ON       t.customer_id = fc.id
GROUP BY fc.domain
