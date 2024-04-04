SELECT
    row_number() OVER () AS id, -- exclude schema to anonymize data
    to_char(DATE_TRUNC('month', date), 'YYYY-MM') AS month,
    MAX(cluster_count) AS total_cluster_count,
    MAX(node_count) AS total_node_count,
    MAX(infra_node_count) AS total_infra_node_count,
    MAX(control_plane_node_count) AS total_control_plane_node_count,
    MAX(worker_node_count) AS total_worker_node_count,
    MAX(infra_node_cpu_cores) AS total_infra_node_cpu_cores,
    MAX(control_plane_node_cpu_cores) AS total_control_plane_node_cpu_cores,
    MAX(worker_node_cpu_cores) AS total_worker_node_cpu_cores,
    MAX(infra_node_mem_gb) AS total_infra_node_mem_gb,
    MAX(control_plane_node_mem_gb) AS total_control_plane_node_mem_gb,
    MAX(worker_node_mem_gb) AS total_worker_node_mem_gb,
    MAX(pvc_count) AS total_pvc_count,
    MAX(cluster_capacity_cores) AS total_cluster_capacity_cores,
    SUM(cluster_capacity_core_hours) AS total_cluster_capacity_core_hours,
    MAX(cluster_capacity_memory_gb) AS total_cluster_capacity_memory_gb,
    SUM(cluster_capacity_memory_gb_hours) AS total_cluster_capacity_memory_gb_hours,
    MAX(volume_request_gb) AS total_volume_request_gb,
    SUM(volume_request_gb_mo) AS total_volume_request_gb_mo,
    MAX(pvc_capacity_gb) AS total_pvc_capacity_gb,
    SUM(pvc_capacity_gb_mo) AS total_pvc_capacity_gb_mo
FROM __cust_openshift_infra_report
GROUP BY schema, DATE_TRUNC('month', date)
ORDER BY schema, DATE_TRUNC('month', date)
;
