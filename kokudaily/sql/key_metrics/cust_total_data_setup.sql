WITH cloud_costs AS (
    SELECT
        date,
        SUM(aws_unblended_cost) AS total_aws_unblended_cost,
        SUM(aws_calculated_amortized_cost) AS total_aws_calculated_amortized_cost,
        SUM(azure_pretax_cost) AS total_azure_pretax_cost,
        SUM(gcp_unblended_cost) AS total_gcp_unblended_cost,
        SUM(gcp_total) AS total_gcp_total,
        SUM(oci_cost) AS total_oci_total
    FROM __cust_cloud_cost_report
    GROUP BY date
),
ocp_costs AS (
    SELECT
        date,
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
    GROUP BY date
),
ocp_infras AS (
    SELECT
        date,
        SUM(cluster_count) AS total_cluster_count,
        SUM(node_count) AS total_node_count,
        SUM(infra_node_count) AS total_infra_node_count,
        SUM(control_plane_node_count) AS total_control_plane_node_count,
        SUM(worker_node_count) AS total_worker_node_count,
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
    GROUP BY date
)
INSERT INTO public.__customer_total_data (
    date,
    total_aws_unblended_cost,
    total_aws_calculated_amortized_cost,
    total_azure_pretax_cost,
    total_gcp_unblended_cost,
    total_gcp_total,
    total_oci_total,
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
    total_pvc_count,
    total_cluster_capacity_cores,
    total_cluster_capacity_core_hours,
    total_cluster_capacity_memory_gb,
    total_cluster_capacity_memory_gb_hours,
    total_volume_request_gb,
    total_volume_request_gb_mo,
    total_pvc_capacity_gb,
    total_pvc_capacity_gb_mo
) SELECT
    date,
    total_aws_unblended_cost,
    total_aws_calculated_amortized_cost,
    total_azure_pretax_cost,
    total_gcp_unblended_cost,
    total_gcp_total,
    total_oci_total,
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
    total_pvc_count,
    total_cluster_capacity_cores,
    total_cluster_capacity_core_hours,
    total_cluster_capacity_memory_gb,
    total_cluster_capacity_memory_gb_hours,
    total_volume_request_gb,
    total_volume_request_gb_mo,
    total_pvc_capacity_gb,
    total_pvc_capacity_gb_mo
FROM cloud_costs cc
FULL OUTER JOIN ocp_costs oc USING (date)
FULL OUTER JOIN ocp_infras oi USING (date)
ORDER BY date
ON CONFLICT (date) DO UPDATE SET
    total_aws_unblended_cost=EXCLUDED.total_aws_unblended_cost,
    total_aws_calculated_amortized_cost=EXCLUDED.total_aws_calculated_amortized_cost,
    total_azure_pretax_cost=EXCLUDED.total_azure_pretax_cost,
    total_gcp_unblended_cost=EXCLUDED.total_gcp_unblended_cost,
    total_gcp_total=EXCLUDED.total_gcp_total,
    total_oci_total=EXCLUDED.total_oci_total,
    total_total_infrastructure_raw_cost=EXCLUDED.total_total_infrastructure_raw_cost,
    total_total_cost_model_costs=EXCLUDED.total_total_cost_model_costs,
    total_infra_total_cost_model=EXCLUDED.total_infra_total_cost_model,
    total_infra_cost_model_cpu_cost=EXCLUDED.total_infra_cost_model_cpu_cost,
    total_infra_cost_model_memory_cost=EXCLUDED.total_infra_cost_model_memory_cost,
    total_infra_cost_model_volume_cost=EXCLUDED.total_infra_cost_model_volume_cost,
    total_sup_total_cost_model=EXCLUDED.total_sup_total_cost_model,
    total_sup_cost_model_cpu_cost=EXCLUDED.total_sup_cost_model_cpu_cost,
    total_sup_cost_model_memory_cost=EXCLUDED.total_sup_cost_model_memory_cost,
    total_sup_cost_model_volume_cost=EXCLUDED.total_sup_cost_model_volume_cost,
    total_cluster_count=EXCLUDED.total_cluster_count,
    total_node_count=EXCLUDED.total_node_count,
    total_pvc_count=EXCLUDED.total_pvc_count,
    total_cluster_capacity_cores=EXCLUDED.total_cluster_capacity_cores,
    total_cluster_capacity_core_hours=EXCLUDED.total_cluster_capacity_core_hours,
    total_cluster_capacity_memory_gb=EXCLUDED.total_cluster_capacity_memory_gb,
    total_cluster_capacity_memory_gb_hours=EXCLUDED.total_cluster_capacity_memory_gb_hours,
    total_volume_request_gb=EXCLUDED.total_volume_request_gb,
    total_volume_request_gb_mo=EXCLUDED.total_volume_request_gb_mo,
    total_pvc_capacity_gb=EXCLUDED.total_pvc_capacity_gb,
    total_pvc_capacity_gb_mo=EXCLUDED.total_pvc_capacity_gb_mo
;
