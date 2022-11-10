WITH cust_non_redhat AS (
    SELECT t.customer_id,
        array_agg(DISTINCT substring(t.email from '@(.*)$')) AS domain
    FROM PUBLIC.api_user t
    WHERE substring(t.email FROM '@(.*)$') != 'redhat.com'
    GROUP BY t.customer_id
),
filtered_customers AS (
    SELECT c.id,
        COALESCE(c.account_id, 'unknown') as account_id,
        c.org_id,
        cnr.domain
    FROM PUBLIC.api_customer c
    JOIN cust_non_redhat AS cnr
        ON cnr.customer_id = c.id
    WHERE c.org_id NOT IN ('11789772','6340056','11009103','1979710','12667745','12667749')
    GROUP BY c.id, cnr.domain
)
SELECT COUNT(DISTINCT p.uuid) as total_cluster_count,
    COUNT(DISTINCT p.uuid) FILTER (WHERE im.infrastructure_type = 'AWS') as ocp_on_aws_cluster_count,
    COUNT(DISTINCT p.uuid) FILTER (WHERE im.infrastructure_type = 'Azure') as ocp_on_azure_cluster_count,
    COUNT(DISTINCT p.uuid) FILTER (WHERE im.infrastructure_type = 'GCP') as ocp_on_gcp_cluster_count,
    COUNT(DISTINCT p.uuid) FILTER (WHERE im.infrastructure_type IS NULL) as ocp_on_prem_cluster_count
FROM public.api_provider as p
LEFT JOIN public.api_providerinfrastructuremap as im
    ON p.infrastructure_id = im.id
JOIN public.api_customer as c
    ON p.customer_id = c.id
JOIN filtered_customers as fc ON p.customer_id = fc.id
WHERE p.type = 'OCP'
    AND p.data_updated_timestamp >= now() - INTERVAL '2 days'
