WITH cte_active_provider_cost_models AS (
    SELECT cmr.*
    FROM __cust_cost_model_report as cmr
    JOIN __active_providers as p
        ON p.uuid = cmr.provider_id

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
        SELECT customer, cost_model_id, cost_model_map_id,
               json_type(cmr.rates, '$[' || element.key || '].tag_rates') AS has_tag_rate
        FROM __cust_cost_model_report cmr
        JOIN json_each(CASE WHEN json_type(rates) = 'array' THEN rates ELSE '[]' END) element
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
        AND json(markup) != '{}'
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
JOIN __customers AS fc
    ON fc.schema_name = cmc.customer
LEFT JOIN cte_tag_rates AS tr
    ON tr.customer = cmc.customer
LEFT JOIN cte_distribution_type AS dt
    ON dt.customer = cmc.customer
LEFT JOIN cte_cloud_markup AS cm
    ON cm.customer = cmc.customer
;
