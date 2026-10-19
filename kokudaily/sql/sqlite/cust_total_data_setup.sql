WITH cloud_costs AS (
    SELECT
        date,
        decimal_sum(aws_unblended_cost) AS total_aws_unblended_cost,
        decimal_sum(aws_calculated_amortized_cost) AS total_aws_calculated_amortized_cost,
        decimal_sum(azure_pretax_cost) AS total_azure_pretax_cost,
        decimal_sum(gcp_unblended_cost) AS total_gcp_unblended_cost,
        decimal_sum(gcp_total) AS total_gcp_total
    FROM __cust_cloud_cost_report
    GROUP BY date
),
ocp_costs AS (
    SELECT
        date,
        decimal_sum(total_infrastructure_raw_cost) AS total_total_infrastructure_raw_cost,
        decimal_sum(total_cost_model_costs) AS total_total_cost_model_costs,
        decimal_sum(infra_total_cost_model) AS total_infra_total_cost_model,
        decimal_sum(infra_cost_model_cpu_cost) AS total_infra_cost_model_cpu_cost,
        decimal_sum(infra_cost_model_memory_cost) AS total_infra_cost_model_memory_cost,
        decimal_sum(infra_cost_model_volume_cost) AS total_infra_cost_model_volume_cost,
        decimal_sum(sup_total_cost_model) AS total_sup_total_cost_model,
        decimal_sum(sup_cost_model_cpu_cost) AS total_sup_cost_model_cpu_cost,
        decimal_sum(sup_cost_model_memory_cost) AS total_sup_cost_model_memory_cost,
        decimal_sum(sup_cost_model_volume_cost) AS total_sup_cost_model_volume_cost
    FROM __cust_openshift_cost_report
    GROUP BY date
),
ocp_infras AS (
    SELECT
        date,
        decimal_sum(cluster_count) AS total_cluster_count,
        decimal_sum(node_count) AS total_node_count,
        decimal_sum(infra_node_count) AS total_infra_node_count,
        decimal_sum(control_plane_node_count) AS total_control_plane_node_count,
        decimal_sum(worker_node_count) AS total_worker_node_count,
        decimal_sum(infra_node_cpu_cores) AS total_infra_node_cpu_cores,
        decimal_sum(control_plane_node_cpu_cores) AS total_control_plane_node_cpu_cores,
        decimal_sum(worker_node_cpu_cores) AS total_worker_node_cpu_cores,
        decimal_sum(infra_node_mem_gb) AS total_infra_node_mem_gb,
        decimal_sum(control_plane_node_mem_gb) AS total_control_plane_node_mem_gb,
        decimal_sum(worker_node_mem_gb) AS total_worker_node_mem_gb,
        decimal_sum(pvc_count) AS total_pvc_count,
        decimal_sum(cluster_capacity_cores) AS total_cluster_capacity_cores,
        decimal_sum(cluster_capacity_core_hours) AS total_cluster_capacity_core_hours,
        decimal_sum(cluster_capacity_memory_gb) AS total_cluster_capacity_memory_gb,
        decimal_sum(cluster_capacity_memory_gb_hours) AS total_cluster_capacity_memory_gb_hours,
        decimal_sum(volume_request_gb) AS total_volume_request_gb,
        decimal_sum(volume_request_gb_mo) AS total_volume_request_gb_mo,
        decimal_sum(pvc_capacity_gb) AS total_pvc_capacity_gb,
        decimal_sum(pvc_capacity_gb_mo) AS total_pvc_capacity_gb_mo
    FROM __cust_openshift_infra_report
    GROUP BY date
)
SELECT
    dates.date,
    total_aws_unblended_cost,
    total_aws_calculated_amortized_cost,
    total_azure_pretax_cost,
    total_gcp_unblended_cost,
    total_gcp_total,
    total_total_infrastructure_raw_cost,
    total_total_cost_model_costs,
    total_infra_total_cost_model,
    total_infra_cost_model_cpu_cost,
    total_infra_cost_model_memory_cost,
    total_infra_cost_model_volume_cost,
    total_sup_total_cost_model,
    total_sup_cost_model_cpu_cost,
    total_sup_cost_model_memory_cost,
    total_sup_cost_model_volume_cost,
    total_cluster_count,
    total_node_count,
    total_infra_node_count,
    total_control_plane_node_count,
    total_worker_node_count,
    total_infra_node_cpu_cores,
    total_control_plane_node_cpu_cores,
    total_worker_node_cpu_cores,
    total_infra_node_mem_gb,
    total_control_plane_node_mem_gb,
    total_worker_node_mem_gb,
    total_pvc_count,
    total_cluster_capacity_cores,
    total_cluster_capacity_core_hours,
    total_cluster_capacity_memory_gb,
    total_cluster_capacity_memory_gb_hours,
    total_volume_request_gb,
    total_volume_request_gb_mo,
    total_pvc_capacity_gb,
    total_pvc_capacity_gb_mo
FROM (SELECT date FROM cloud_costs UNION SELECT date FROM ocp_costs
      UNION SELECT date FROM ocp_infras) dates
LEFT JOIN cloud_costs cc USING (date)
LEFT JOIN ocp_costs oc USING (date)
LEFT JOIN ocp_infras oi USING (date)
ORDER BY date;
