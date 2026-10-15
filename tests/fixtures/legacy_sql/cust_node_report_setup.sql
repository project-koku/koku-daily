DROP TABLE IF EXISTS __cust_node_report;
-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_node_report (
    customer text,
    provider_id text,
    cluster_id text,
    node text,
    report_month date,
    cpu_cores bigint,
    memory_gigabytes bigint
);
CREATE INDEX ix__cust_node_report ON __cust_node_report (customer, provider_id, cluster_id, node, report_month);
