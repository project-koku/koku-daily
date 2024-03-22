SELECT
    to_char(DATE_TRUNC('month', date), 'YYYY-MM') AS month,
    SUM(total_aws_unblended_cost) AS total_aws_unblended_cost,
    SUM(total_aws_calculated_amortized_cost) AS total_aws_calculated_amortized_cost,
    SUM(total_azure_pretax_cost) AS total_azure_pretax_cost,
    SUM(total_gcp_unblended_cost) AS total_gcp_unblended_cost,
    SUM(total_gcp_total) AS total_gcp_total,
    SUM(total_oci_total) AS total_oci_total,
    SUM(total_total_infrastructure_raw_cost) AS total_total_infrastructure_raw_cost,
    SUM(total_total_cost_model_costs) AS total_total_cost_model_costs,
    SUM(total_infra_total_cost_model) AS total_infra_total_cost_model,
    SUM(total_infra_cost_model_cpu_cost) AS total_infra_cost_model_cpu_cost,
    SUM(total_infra_cost_model_memory_cost) AS total_infra_cost_model_memory_cost,
    SUM(total_infra_cost_model_volume_cost) AS total_infra_cost_model_volume_cost,
    SUM(total_sup_total_cost_model) AS total_sup_total_cost_model,
    SUM(total_sup_cost_model_cpu_cost) AS total_sup_cost_model_cpu_cost,
    SUM(total_sup_cost_model_memory_cost) AS total_sup_cost_model_memory_cost,
    SUM(total_sup_cost_model_volume_cost) AS total_sup_cost_model_volume_cost,
    MAX(total_cluster_count) AS total_cluster_count,
    MAX(total_node_count) AS total_node_count,
    MAX(total_pvc_count) AS total_pvc_count,
    MAX(total_cluster_capacity_cores) AS total_cluster_capacity_cores,
    MAX(total_cluster_capacity_core_hours) AS total_cluster_capacity_core_hours,
    MAX(total_cluster_capacity_memory_gb) AS total_cluster_capacity_memory_gb,
    MAX(total_cluster_capacity_memory_gb_hours) AS total_cluster_capacity_memory_gb_hours,
    MAX(total_volume_request_gb) AS total_volume_request_gb,
    SUM(total_volume_request_gb_mo) AS total_volume_request_gb_mo,
    MAX(total_pvc_capacity_gb) AS total_pvc_capacity_gb,
    SUM(total_pvc_capacity_gb_mo) AS total_pvc_capacity_gb_mo
FROM public.__customer_total_data
GROUP BY DATE_TRUNC('month', date)
ORDER BY DATE_TRUNC('month', date)
;
