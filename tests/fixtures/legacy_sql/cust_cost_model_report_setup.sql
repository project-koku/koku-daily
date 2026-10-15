DROP TABLE IF EXISTS __cust_cost_model_report;
-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_cost_model_report (
    customer text,
    cost_model_id text,
    source_type text,
    created_timestamp date,
    updated_timestamp date,
    rates jsonb,
    markup jsonb,
    distribution text,
    cost_model_map_id text,
    provider_id text,
    cluster_id text
);
