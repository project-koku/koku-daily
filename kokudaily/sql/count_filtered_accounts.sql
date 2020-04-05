 WITH cust_non_redhat AS
(
                SELECT DISTINCT t.customer_id
                FROM            PUBLIC.api_user t
                WHERE           substring(t.email from '@(.*)$') != 'redhat.com' )
SELECT count(DISTINCT c.account_id)
FROM   PUBLIC.api_customer c
JOIN   cust_non_redhat AS cnr
ON     cnr.customer_id = c.id
WHERE  c.account_id NOT IN ('6089719',
                            '1460290',
                            '5910538',
                            '540155',
                            '6289400',
                            '6289401')
