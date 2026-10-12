insert
  into __cust_tag_report (
    customer,
    openshift_label_key_count,
    aws_tag_key_count,
    azure_tag_key_count,
    gcp_label_key_count
  )
  with cte_openshift_label_count AS (
    select count(distinct key) as key_count
    from {schema}.reporting_ocptags_values
  ),
  cte_aws_tag_count AS (
    select count(distinct key) as key_count
    from {schema}.reporting_awstags_values
  ),
  cte_azure_tag_count AS (
    select count(distinct key) as key_count
    from {schema}.reporting_azuretags_values
  ),
  cte_gcp_label_count AS (
    select count(distinct key) as key_count
    from {schema}.reporting_gcptags_values
  )
  select :customer as "customer",
    ocp.key_count as openshift_label_key_count,
    aws.key_count as aws_tag_key_count,
    azure.key_count as azure_tag_key_count,
    gcp.key_count as gcp_label_key_count
  from cte_openshift_label_count as ocp
  cross join cte_aws_tag_count as aws
  cross join cte_azure_tag_count as azure
  cross join cte_gcp_label_count as gcp
  ;
