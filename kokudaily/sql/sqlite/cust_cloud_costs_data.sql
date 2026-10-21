select
    md5(schema) AS id, -- exclude schema to anonymize data
    substr(date, 1, 7) AS month,
    decimal_sum(aws_unblended_cost) AS "aws_unblended_cost",
    decimal_sum(aws_calculated_amortized_cost) AS "aws_calculated_amortized_cost",
    decimal_sum(azure_pretax_cost) AS "azure_pretax_cost",
    decimal_sum(gcp_unblended_cost) AS "gcp_unblended_cost",
    decimal_sum(gcp_total) AS "gcp_total"
from __cust_cloud_cost_report
GROUP BY schema, substr(date, 1, 7)
ORDER BY schema, substr(date, 1, 7)
;
