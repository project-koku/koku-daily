 WITH cust_non_redhat AS
(
                SELECT DISTINCT t.customer_id
                FROM            PUBLIC.api_user t
                WHERE           substring(t.email from '@(.*)$') != 'redhat.com' )
SELECT count(DISTINCT c.org_id)
FROM   PUBLIC.api_customer c
JOIN   cust_non_redhat AS cnr
ON     cnr.customer_id = c.id
WHERE    c.org_id NOT IN ('11789772',
                          '6340056',
                          '11009103',
                          '1979710',
                          '12667745',
                          '12667749')
;
