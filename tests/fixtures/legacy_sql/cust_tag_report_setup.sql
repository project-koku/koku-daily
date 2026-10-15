drop table if exists __cust_tag_report;
-- create temp table for results
create temporary table if not exists __cust_tag_report (
    customer text,
    openshift_label_key_count bigint,
    aws_tag_key_count bigint,
    azure_tag_key_count bigint,
    gcp_label_key_count bigint
);
