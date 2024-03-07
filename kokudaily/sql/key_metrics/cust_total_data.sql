WITH number_of_days AS (
    SELECT
        month,
        CASE
            WHEN extract(month FROM month) = extract(month FROM CURRENT_DATE) THEN extract(days FROM CURRENT_DATE)
            ELSE extract(days FROM date_trunc('month', month) + '1 month - 1 day'::interval)
        END AS days
    FROM __cust_cloud_cost_report
    GROUP BY month
),
cloud_costs AS (
    SELECT
        month,
        SUM(aws_unblended_cost) AS total_aws_unblended_cost,
        SUM(aws_calculated_amortized_cost) AS total_aws_calculated_amortized_cost,
        SUM(azure_pretax_cost) AS total_azure_pretax_cost,
        SUM(gcp_unblended_cost) AS total_gcp_unblended_cost,
        SUM(gcp_total) AS total_gcp_total,
        SUM(oci_cost) AS total_oci_total
    FROM __cust_cloud_cost_report
    GROUP BY month
),
ocp_costs AS (
    SELECT
        month,
        SUM(total_infrastructure_raw_cost) AS total_total_infrastructure_raw_cost,
        SUM(total_cost_model_costs) AS total_total_cost_model_costs,
        SUM(infra_total_cost_model) AS total_infra_total_cost_model,
        SUM(infra_cost_model_cpu_cost) AS total_infra_cost_model_cpu_cost,
        SUM(infra_cost_model_memory_cost) AS total_infra_cost_model_memory_cost,
        SUM(infra_cost_model_volume_cost) AS total_infra_cost_model_volume_cost,
        SUM(sup_total_cost_model) AS total_sup_total_cost_model,
        SUM(sup_cost_model_cpu_cost) AS total_sup_cost_model_cpu_cost,
        SUM(sup_cost_model_memory_cost) AS total_sup_cost_model_memory_cost,
        SUM(sup_cost_model_volume_cost) AS total_sup_cost_model_volume_cost
    FROM __cust_openshift_cost_report
    GROUP BY month
),
ocp_infras AS (
    SELECT
        month,
        SUM(cluster_count) AS total_cluster_count,
        SUM(node_count) AS total_node_count,
        SUM(pvc_count) AS total_pvc_count,
        SUM(cluster_capacity_cores) AS total_cluster_capacity_cores,
        SUM(cluster_capacity_core_hours) AS total_cluster_capacity_core_hours,
        SUM(cluster_capacity_memory_gb) AS total_cluster_capacity_memory_gb,
        SUM(cluster_capacity_memory_gb_hours) AS total_cluster_capacity_memory_gb_hours,
        SUM(volume_request_gb) AS total_volume_request_gb,
        SUM(volume_request_gb_mo) AS total_volume_request_gb_mo,
        SUM(pvc_capacity_gb) AS total_pvc_capacity_gb,
        SUM(pvc_capacity_gb_mo) AS total_pvc_capacity_gb_mo
    FROM __cust_openshift_infra_report
    GROUP BY month
)
SELECT
    month,
    days,
    total_aws_unblended_cost,
    total_aws_unblended_cost_per_day,
    total_aws_calculated_amortized_cost,
    total_aws_calculated_amortized_cost_per_day,
    total_azure_pretax_cost,
    total_azure_pretax_cost_per_day,
    total_gcp_unblended_cost,
    total_gcp_unblended_cost_per_day,
    total_gcp_total,
    total_gcp_total_per_day,
    total_oci_total,
    total_oci_total_per_day,
    total_total_infrastructure_raw_cost,
    total_total_infrastructure_raw_cost_per_day,
    total_total_cost_model_costs,
    total_total_cost_model_costs_per_day,
    total_infra_total_cost_model,
    total_infra_total_cost_model_per_day,
    total_infra_cost_model_cpu_cost,
    total_infra_cost_model_cpu_cost_per_day,
    total_infra_cost_model_memory_cost,
    total_infra_cost_model_memory_cost_per_day,
    total_infra_cost_model_volume_cost,
    total_infra_cost_model_volume_cost_per_day,
    total_sup_total_cost_model,
    total_sup_total_cost_model_per_day,
    total_sup_cost_model_cpu_cost,
    total_sup_cost_model_cpu_cost_per_day,
    total_sup_cost_model_memory_cost,
    total_sup_cost_model_memory_cost_per_day,
    total_sup_cost_model_volume_cost,
    total_sup_cost_model_volume_cost_per_day,
    total_cluster_count,
    total_node_count,
    total_pvc_count,
    total_cluster_capacity_cores,
    total_cluster_capacity_core_hours,
    total_cluster_capacity_memory_gb,
    total_cluster_capacity_memory_gb_hours,
    total_volume_request_gb,
    total_volume_request_gb_mo,
    total_pvc_capacity_gb,
    total_pvc_capacity_gb_mo
FROM (
    (SELECT
        to_char(month, 'YYYY-MM') AS month,
        days,
        total_aws_unblended_cost,
        (total_aws_unblended_cost/days)::numeric(33, 2) AS total_aws_unblended_cost_per_day,
        total_aws_calculated_amortized_cost,
        (total_aws_calculated_amortized_cost/days)::numeric(33, 2) AS total_aws_calculated_amortized_cost_per_day,
        total_azure_pretax_cost,
        (total_azure_pretax_cost/days)::numeric(33, 2) AS total_azure_pretax_cost_per_day,
        total_gcp_unblended_cost,
        (total_gcp_unblended_cost/days)::numeric(33, 2) AS total_gcp_unblended_cost_per_day,
        total_gcp_total,
        (total_gcp_total/days)::numeric(33, 2) AS total_gcp_total_per_day,
        total_oci_total,
        (total_oci_total/days)::numeric(33, 2) AS total_oci_total_per_day,
        total_total_infrastructure_raw_cost,
        (total_total_infrastructure_raw_cost/days)::numeric(33, 2) AS total_total_infrastructure_raw_cost_per_day,
        total_total_cost_model_costs,
        (total_total_cost_model_costs/days)::numeric(33, 2) AS total_total_cost_model_costs_per_day,
        total_infra_total_cost_model,
        (total_infra_total_cost_model/days)::numeric(33, 2) AS total_infra_total_cost_model_per_day,
        total_infra_cost_model_cpu_cost,
        (total_infra_cost_model_cpu_cost/days)::numeric(33, 2) AS total_infra_cost_model_cpu_cost_per_day,
        total_infra_cost_model_memory_cost,
        (total_infra_cost_model_memory_cost/days)::numeric(33, 2) AS total_infra_cost_model_memory_cost_per_day,
        total_infra_cost_model_volume_cost,
        (total_infra_cost_model_volume_cost/days)::numeric(33, 2) AS total_infra_cost_model_volume_cost_per_day,
        total_sup_total_cost_model,
        (total_sup_total_cost_model/days)::numeric(33, 2) AS total_sup_total_cost_model_per_day,
        total_sup_cost_model_cpu_cost,
        (total_sup_cost_model_cpu_cost/days)::numeric(33, 2) AS total_sup_cost_model_cpu_cost_per_day,
        total_sup_cost_model_memory_cost,
        (total_sup_cost_model_memory_cost/days)::numeric(33, 2) AS total_sup_cost_model_memory_cost_per_day,
        total_sup_cost_model_volume_cost,
        (total_sup_cost_model_volume_cost/days)::numeric(33, 2) AS total_sup_cost_model_volume_cost_per_day,
        total_cluster_count,
        total_node_count,
        total_pvc_count,
        total_cluster_capacity_cores,
        total_cluster_capacity_core_hours,
        total_cluster_capacity_memory_gb,
        total_cluster_capacity_memory_gb_hours,
        total_volume_request_gb,
        total_volume_request_gb_mo,
        total_pvc_capacity_gb,
        total_pvc_capacity_gb_mo,
        month AS sort_order
    FROM cloud_costs cc
    FULL OUTER JOIN number_of_days nod USING (month)
    FULL OUTER JOIN ocp_costs oc USING (month)
    FULL OUTER JOIN ocp_infras oi USING (month)
    ORDER BY month)

    UNION

    (SELECT
        'TOTAL' AS month,
        SUM(days) AS days,
        SUM(total_aws_unblended_cost) AS total_aws_unblended_cost,
        (SUM(total_aws_unblended_cost)/SUM(days))::numeric(33, 2) AS total_aws_unblended_cost_per_day,
        SUM(total_aws_calculated_amortized_cost) AS total_aws_calculated_amortized_cost,
        (SUM(total_aws_calculated_amortized_cost)/SUM(days))::numeric(33, 2) AS total_aws_calculated_amortized_cost_per_day,
        SUM(total_azure_pretax_cost) AS total_azure_pretax_cost,
        (SUM(total_azure_pretax_cost)/SUM(days))::numeric(33, 2) AS total_azure_pretax_cost_per_day,
        SUM(total_gcp_unblended_cost) AS total_gcp_unblended_cost,
        (SUM(total_gcp_unblended_cost)/SUM(days))::numeric(33, 2) AS total_gcp_unblended_cost_per_day,
        SUM(total_gcp_total) AS total_gcp_total,
        (SUM(total_gcp_total)/SUM(days))::numeric(33, 2) AS total_gcp_total_per_day,
        SUM(total_oci_total) AS total_oci_total,
        (SUM(total_oci_total)/SUM(days))::numeric(33, 2) AS total_oci_total_per_day,
        SUM(total_total_infrastructure_raw_cost) AS total_total_infrastructure_raw_cost,
        (SUM(total_total_infrastructure_raw_cost)/SUM(days))::numeric(33, 2) AS total_total_infrastructure_raw_cost_per_day,
        SUM(total_total_cost_model_costs) AS total_total_cost_model_costs,
        (SUM(total_total_cost_model_costs)/SUM(days))::numeric(33, 2) AS total_total_cost_model_costs_per_day,
        SUM(total_infra_total_cost_model) AS total_infra_total_cost_model,
        (SUM(total_infra_total_cost_model)/SUM(days))::numeric(33, 2) AS total_infra_total_cost_model_per_day,
        SUM(total_infra_cost_model_cpu_cost) AS total_infra_cost_model_cpu_cost,
        (SUM(total_infra_cost_model_cpu_cost)/SUM(days))::numeric(33, 2) AS total_infra_cost_model_cpu_cost_per_day,
        SUM(total_infra_cost_model_memory_cost) AS total_infra_cost_model_memory_cost,
        (SUM(total_infra_cost_model_memory_cost)/SUM(days))::numeric(33, 2) AS total_infra_cost_model_memory_cost_per_day,
        SUM(total_infra_cost_model_volume_cost) AS total_infra_cost_model_volume_cost,
        (SUM(total_infra_cost_model_volume_cost)/SUM(days))::numeric(33, 2) AS total_infra_cost_model_volume_cost_per_day,
        SUM(total_sup_total_cost_model) AS total_sup_total_cost_model,
        (SUM(total_sup_total_cost_model)/SUM(days))::numeric(33, 2) AS total_sup_total_cost_model_per_day,
        SUM(total_sup_cost_model_cpu_cost) AS total_sup_cost_model_cpu_cost,
        (SUM(total_sup_cost_model_cpu_cost)/SUM(days))::numeric(33, 2) AS total_sup_cost_model_cpu_cost_per_day,
        SUM(total_sup_cost_model_memory_cost) AS total_sup_cost_model_memory_cost,
        (SUM(total_sup_cost_model_memory_cost)/SUM(days))::numeric(33, 2) AS total_sup_cost_model_memory_cost_per_day,
        SUM(total_sup_cost_model_volume_cost) AS total_sup_cost_model_volume_cost,
        (SUM(total_sup_cost_model_volume_cost)/SUM(days))::numeric(33, 2) AS total_sup_cost_model_volume_cost_per_day,
        null AS total_cluster_count,
        null AS total_node_count,
        null AS total_pvc_count,
        null AS total_cluster_capacity_cores,
        null AS total_cluster_capacity_core_hours,
        null AS total_cluster_capacity_memory_gb,
        null AS total_cluster_capacity_memory_gb_hours,
        null AS total_volume_request_gb,
        null AS total_volume_request_gb_mo,
        null AS total_pvc_capacity_gb,
        null AS total_pvc_capacity_gb_mo,
        '9999-12-31'::date AS sort_order
    FROM cloud_costs cc
    FULL OUTER JOIN number_of_days nod USING (month)
    FULL OUTER JOIN ocp_costs oc USING (month)
    FULL OUTER JOIN ocp_infras oi USING (month))
) AS unionquery
ORDER BY sort_order
;
