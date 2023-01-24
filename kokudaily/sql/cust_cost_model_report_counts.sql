WITH cust_non_redhat AS (
    SELECT u.customer_id,
           array_agg(DISTINCT substring(u.email FROM '@(.*)$')) AS domain
    FROM   public.api_user u
    WHERE  substring(u.email FROM '@(.*)$') != 'redhat.com'
    GROUP
       BY  u.customer_id
),
filtered_customers AS (
    SELECT c.id,
           coalesce(c.account_id, 'unknown') AS account_id,
           c.org_id,
           c.schema_name,
           cnr.domain
    FROM   public.api_customer c
    JOIN   cust_non_redhat AS cnr
    ON     cnr.customer_id = c.id
    WHERE  c.org_id NOT IN ('11789772',
                            '6340056',
                            '11009103',
                            '1979710',
                            '12667745',
                            '12667749')
    GROUP
       BY  c.id,
           cnr.domain
),
cte_active_provider_cost_models AS (
    SELECT cmr.*
    FROM __cust_cost_model_report as cmr
    JOIN public.api_provider as p
        ON p.uuid::text = cmr.provider_id
    WHERE p.data_updated_timestamp >= now() - interval '48 HOURS'
),
cte_cost_model_customers AS (
    SELECT DISTINCT customer
    FROM cte_active_provider_cost_models
),
cte_tag_rates AS (
    SELECT customer,
        count(DISTINCT cost_model_id) as count_total_cost_models_with_tag_rates,
        count(DISTINCT cost_model_id) FILTER (WHERE cost_model_map_id IS NOT NULL) as count_active_cost_models_with_tag_rates,
        count(DISTINCT cost_model_id) FILTER (WHERE cost_model_map_id IS NULL) as count_inactive_cost_models_with_tag_rates
    FROM (
        SELECT customer, cost_model_id, cost_model_map_id, jsonb_array_elements(rates)->'tag_rates' as has_tag_rate
        FROM __cust_cost_model_report cmr
    ) as sub
    WHERE has_tag_rate IS NOT NULL
    GROUP BY customer
),
cte_distribution_type AS (
    SELECT customer,
        count(distribution) FILTER (WHERE distribution='cpu') as count_total_cost_models_cpu_distribution,
        count(distribution) FILTER (WHERE distribution='cpu' AND cost_model_map_id IS NOT NULL) as count_active_cost_models_cpu_distribution,
        count(distribution) FILTER (WHERE distribution='cpu' AND cost_model_map_id IS NULL) as count_inactive_cost_models_cpu_distribution,
        count(distribution) FILTER (WHERE distribution='memory') as count_total_cost_models_memory_distribution,
        count(distribution) FILTER (WHERE distribution='memory' AND cost_model_map_id IS NOT NULL) as count_active_cost_models_memory_distribution,
        count(distribution) FILTER (WHERE distribution='memory' AND cost_model_map_id IS NULL) as count_inactive_cost_models_memory_distribution
    FROM __cust_cost_model_report cmr
    WHERE source_type = 'OCP'
    GROUP BY customer
),
cte_cloud_markup AS (
    SELECT customer,
        count(DISTINCT cost_model_id) as count_total_cost_models_with_cloud_markup,
        count(DISTINCT cost_model_id) FILTER (WHERE cost_model_map_id IS NOT NULL) as count_active_cost_models_with_cloud_markup,
        count(DISTINCT cost_model_id) FILTER (WHERE cost_model_map_id IS NULL) as count_inactive_cost_models_with_cloud_markup
    FROM __cust_cost_model_report cmr
    WHERE source_type != 'OCP'
        AND markup != '{}'::jsonb
    GROUP BY customer
)
SELECT fc.account_id,
    fc.org_id,
    fc.schema_name,
    fc.domain,
    tr.count_total_cost_models_with_tag_rates,
    tr.count_active_cost_models_with_tag_rates,
    tr.count_inactive_cost_models_with_tag_rates,
    dt.count_total_cost_models_cpu_distribution,
    dt.count_active_cost_models_cpu_distribution,
    dt.count_inactive_cost_models_cpu_distribution,
    dt.count_total_cost_models_memory_distribution,
    dt.count_active_cost_models_memory_distribution,
    dt.count_inactive_cost_models_memory_distribution,
    cm.count_total_cost_models_with_cloud_markup,
    cm.count_active_cost_models_with_cloud_markup,
    cm.count_inactive_cost_models_with_cloud_markup
FROM cte_cost_model_customers cmc
JOIN filtered_customers AS fc
    ON fc.schema_name = cmc.customer
LEFT JOIN cte_tag_rates AS tr
    ON tr.customer = cmc.customer
LEFT JOIN cte_distribution_type AS dt
    ON dt.customer = cmc.customer
LEFT JOIN cte_cloud_markup AS cm
    ON cm.customer = cmc.customer
;
