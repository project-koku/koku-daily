"Typed Python intermediates matching the former staging table columns."

SETUP_TABLES = {
    "sql/cust_cost_model_report_setup_schema.sql": (
        "__cust_cost_model_report"
    ),
    "sql/cust_node_report_setup_schema.sql": ("__cust_node_report"),
    "sql/cust_tag_report_setup_schema.sql": ("__cust_tag_report"),
    "sql/key_metrics/cust_cloud_costs_data_setup_schema.sql": (
        "__cust_cloud_cost_report"
    ),
    "sql/key_metrics/cust_openshift_costs_data_setup_schema.sql": (
        "__cust_openshift_cost_report"
    ),
    "sql/key_metrics/cust_openshift_infra_data_setup_schema.sql": (
        "__cust_openshift_infra_report"
    ),
}

DEFINITIONS = {
    "__cust_cloud_cost_report": (
        "schema text, date date, aws_unblended_cost numeric(33, 2), "
        "aws_calculated_amortized_cost numeric(33, 2), azure_pretax_cost "
        "numeric(33, 2), gcp_unblended_cost numeric(33, 2), gcp_total "
        "numeric(33, 2)"
    ),
    "__cust_cost_model_report": (
        "customer text, cost_model_id text, source_type text, "
        "created_timestamp date, updated_timestamp date, rates jsonb, "
        "markup jsonb, distribution text, cost_model_map_id text, "
        "provider_id text, cluster_id text"
    ),
    "__cust_node_report": (
        "customer text, provider_id text, cluster_id text, node text, "
        "report_month date, cpu_cores bigint, memory_gigabytes bigint"
    ),
    "__cust_openshift_cost_report": (
        "schema text, date date, total_infrastructure_raw_cost "
        "numeric(33, 2), total_cost_model_costs numeric(33, 2), "
        "infra_total_cost_model numeric(33, 2), infra_cost_model_cpu_cost"
        " numeric(33, 2), infra_cost_model_memory_cost numeric(33, 2), "
        "infra_cost_model_volume_cost numeric(33, 2), "
        "sup_total_cost_model numeric(33, 2), sup_cost_model_cpu_cost "
        "numeric(33, 2), sup_cost_model_memory_cost numeric(33, 2), "
        "sup_cost_model_volume_cost numeric(33, 2)"
    ),
    "__cust_openshift_infra_report": (
        "schema text, date date, cluster_count integer, node_count "
        "integer, architecture text, infra_node_count integer, "
        "control_plane_node_count integer, worker_node_count integer, "
        "infra_node_cpu_cores numeric(33, 2), "
        "control_plane_node_cpu_cores numeric(33, 2), "
        "worker_node_cpu_cores numeric(33, 2), infra_node_mem_gb "
        "numeric(33, 2), control_plane_node_mem_gb numeric(33, 2), "
        "worker_node_mem_gb numeric(33, 2), pvc_count integer, "
        "cluster_capacity_cores numeric(33, 2), "
        "cluster_capacity_core_hours numeric(33, 2), "
        "cluster_capacity_memory_gb numeric(33, 2), "
        "cluster_capacity_memory_gb_hours numeric(33, 2), "
        "volume_request_gb numeric(33, 2), volume_request_gb_mo "
        "numeric(33, 2), pvc_capacity_gb numeric(33, 2), "
        "pvc_capacity_gb_mo numeric(33, 2)"
    ),
    "__cust_tag_report": (
        "customer text, openshift_label_key_count bigint, "
        "aws_tag_key_count bigint, azure_tag_key_count bigint, "
        "gcp_label_key_count bigint"
    ),
    "__customer_total_data": ("public.__customer_total_data"),
}
