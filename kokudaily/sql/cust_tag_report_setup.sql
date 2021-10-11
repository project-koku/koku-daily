drop table if exists __cust_tag_report;
-- create temp table for results
create temporary table if not exists __cust_tag_report (
    customer text,
    openshift_label_key_count bigint,
    aws_tag_key_count bigint,
    azure_tag_key_count bigint,
    gcp_label_key_count bigint
);
-- loop construct
do $BODY$
declare
    schema_rec record;
    -- OCP data gather per-schema
    stmt_tmpl text = '
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
    from %%1$s.reporting_ocptags_values
  ),
  cte_aws_tag_count AS (
    select count(distinct key) as key_count
    from %%1$s.reporting_awstags_values
  ),
  cte_azure_tag_count AS (
    select count(distinct key) as key_count
    from %%1$s.reporting_azuretags_values
  ),
  cte_gcp_label_count AS (
    select count(distinct key) as key_count
    from %%1$s.reporting_gcptags_values
  )
  select ''%%1$s'' as "customer",
    ocp.key_count as openshift_label_key_count,
    aws.key_count as aws_tag_key_count,
    azure.key_count as azure_tag_key_count,
    gcp.key_count as gcp_label_key_count
  from cte_openshift_label_count as ocp
  cross join cte_aws_tag_count as aws
  cross join cte_azure_tag_count as azure
  cross join cte_gcp_label_count as gcp
  ;
';
begin
    for schema_rec in
        select distinct t.schema_name
          from public.api_tenant t
          join pg_namespace n
            on n.nspname = t.schema_name
          join public.api_customer c
            on c.schema_name = t.schema_name
          where t.schema_name ~ '^acct'
          order
            by t.schema_name
    loop
        execute format(stmt_tmpl, schema_rec.schema_name);
    end loop;
end $BODY$ language plpgsql;
