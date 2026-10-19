SELECT
    md5(schema) AS id, -- exclude schema to anonymize data
    substr(date, 1, 7) AS month,
    MAX(cluster_count) AS total_cluster_count,
    MAX(node_count) AS total_node_count,
    architecture AS node_architecture,
    MAX(infra_node_count) AS total_infra_node_count,
    MAX(control_plane_node_count) AS total_control_plane_node_count,
    MAX(worker_node_count) AS total_worker_node_count,
    decimal_max(infra_node_cpu_cores) AS total_infra_node_cpu_cores,
    decimal_max(control_plane_node_cpu_cores) AS total_control_plane_node_cpu_cores,
    decimal_max(worker_node_cpu_cores) AS total_worker_node_cpu_cores,
    decimal_max(infra_node_mem_gb) AS total_infra_node_mem_gb,
    decimal_max(control_plane_node_mem_gb) AS total_control_plane_node_mem_gb,
    decimal_max(worker_node_mem_gb) AS total_worker_node_mem_gb,
    MAX(pvc_count) AS total_pvc_count,
    decimal_max(cluster_capacity_cores) AS total_cluster_capacity_cores,
    decimal_sum(cluster_capacity_core_hours) AS total_cluster_capacity_core_hours,
    decimal_max(cluster_capacity_memory_gb) AS total_cluster_capacity_memory_gb,
    decimal_sum(cluster_capacity_memory_gb_hours) AS total_cluster_capacity_memory_gb_hours,
    decimal_max(volume_request_gb) AS total_volume_request_gb,
    decimal_sum(volume_request_gb_mo) AS total_volume_request_gb_mo,
    decimal_max(pvc_capacity_gb) AS total_pvc_capacity_gb,
    decimal_sum(pvc_capacity_gb_mo) AS total_pvc_capacity_gb_mo
FROM __cust_openshift_infra_report
GROUP BY schema, substr(date, 1, 7), architecture
ORDER BY schema, substr(date, 1, 7), architecture NULLS LAST
;
