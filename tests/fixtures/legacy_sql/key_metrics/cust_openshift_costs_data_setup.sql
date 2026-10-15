DROP TABLE IF EXISTS __cust_openshift_cost_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_openshift_cost_report (
    schema text,
    date date,
    total_infrastructure_raw_cost numeric(33, 2),
    total_cost_model_costs numeric(33, 2),
    infra_total_cost_model numeric(33, 2),
    infra_cost_model_cpu_cost numeric(33, 2),
    infra_cost_model_memory_cost numeric(33, 2),
    infra_cost_model_volume_cost numeric(33, 2),
    sup_total_cost_model numeric(33, 2),
    sup_cost_model_cpu_cost numeric(33, 2),
    sup_cost_model_memory_cost numeric(33, 2),
    sup_cost_model_volume_cost numeric(33, 2)
);
