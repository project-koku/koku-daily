DROP TABLE IF EXISTS __cust_cloud_cost_report;

-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_cloud_cost_report (
    schema text,
    date date,
    aws_unblended_cost numeric(33, 2),
    aws_calculated_amortized_cost numeric(33, 2),
    azure_pretax_cost numeric(33, 2),
    gcp_unblended_cost numeric(33, 2),
    gcp_total numeric(33, 2)
);
