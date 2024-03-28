SELECT
    to_char(DATE_TRUNC('month', date), 'YYYY-MM') AS month,
    SUM(cluster_count) AS total_cluster_count,
    SUM(node_count) AS total_node_count,
    SUM(infra_node_count) AS total_infra_node_count,
    SUM(control_plane_node_count) AS total_control_plane_node_count,
    SUM(worker_node_count) AS total_worker_node_count,
    SUM(infra_node_cpu_cores) AS total_infra_node_cpu_cores,
    SUM(control_plane_node_cpu_cores) AS total_control_plane_node_cpu_cores,
    SUM(worker_node_cpu_cores) AS total_worker_node_cpu_cores,
    SUM(infra_node_mem_gb) AS total_infra_node_mem_gb,
    SUM(control_plane_node_mem_gb) AS total_control_plane_node_mem_gb,
    SUM(worker_node_mem_gb) AS total_worker_node_mem_gb,
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
GROUP BY DATE_TRUNC('month', date)
ORDER BY DATE_TRUNC('month', date)
;
