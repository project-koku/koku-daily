DROP TABLE IF EXISTS __cust_openshift_infra_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_openshift_infra_report (
    schema text,
    date date,
    cluster_count integer,
    node_count integer,
    architecture text,
    infra_node_count integer,
    control_plane_node_count integer,
    worker_node_count integer,
    infra_node_cpu_cores numeric(33, 2),
    control_plane_node_cpu_cores numeric(33, 2),
    worker_node_cpu_cores numeric(33, 2),
    infra_node_mem_gb numeric(33, 2),
    control_plane_node_mem_gb numeric(33, 2),
    worker_node_mem_gb numeric(33, 2),
    pvc_count integer,
    cluster_capacity_cores numeric(33, 2),
    cluster_capacity_core_hours numeric(33, 2),
    cluster_capacity_memory_gb numeric(33, 2),
    cluster_capacity_memory_gb_hours numeric(33, 2),
    volume_request_gb numeric(33, 2),
    volume_request_gb_mo numeric(33, 2),
    pvc_capacity_gb numeric(33, 2),
    pvc_capacity_gb_mo numeric(33, 2)
);
