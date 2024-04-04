select
    row_number() OVER () AS id,
    to_char(DATE_TRUNC('month', date), 'YYYY-MM') AS month,
    SUM(total_infrastructure_raw_cost) AS "total_infrastructure_raw_cost",
    SUM(total_cost_model_costs) AS "total_cost_model_costs",
    SUM(infra_total_cost_model) AS "infra_total_cost_model",
    SUM(infra_cost_model_cpu_cost) AS "infra_cost_model_cpu_cost",
    SUM(infra_cost_model_memory_cost) AS "infra_cost_model_memory_cost",
    SUM(infra_cost_model_volume_cost) AS "infra_cost_model_volume_cost",
    SUM(sup_total_cost_model) AS "sup_total_cost_model",
    SUM(sup_cost_model_cpu_cost) AS "sup_cost_model_cpu_cost",
    SUM(sup_cost_model_memory_cost) AS "sup_cost_model_memory_cost",
    SUM(sup_cost_model_volume_cost) AS "sup_cost_model_volume_cost"
from __cust_openshift_cost_report
GROUP BY schema, DATE_TRUNC('month', date)
ORDER BY schema, DATE_TRUNC('month', date)
;
