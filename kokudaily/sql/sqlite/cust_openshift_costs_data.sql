select
    md5(schema) AS id, -- exclude schema to anonymize data
    substr(date, 1, 7) AS month,
    decimal_sum(total_infrastructure_raw_cost) AS "total_infrastructure_raw_cost",
    decimal_sum(total_cost_model_costs) AS "total_cost_model_costs",
    decimal_sum(infra_total_cost_model) AS "infra_total_cost_model",
    decimal_sum(infra_cost_model_cpu_cost) AS "infra_cost_model_cpu_cost",
    decimal_sum(infra_cost_model_memory_cost) AS "infra_cost_model_memory_cost",
    decimal_sum(infra_cost_model_volume_cost) AS "infra_cost_model_volume_cost",
    decimal_sum(sup_total_cost_model) AS "sup_total_cost_model",
    decimal_sum(sup_cost_model_cpu_cost) AS "sup_cost_model_cpu_cost",
    decimal_sum(sup_cost_model_memory_cost) AS "sup_cost_model_memory_cost",
    decimal_sum(sup_cost_model_volume_cost) AS "sup_cost_model_volume_cost"
from __cust_openshift_cost_report
GROUP BY schema, substr(date, 1, 7)
ORDER BY schema, substr(date, 1, 7)
;
