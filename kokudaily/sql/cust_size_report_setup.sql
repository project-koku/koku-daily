drop table if exists __cust_size_report;
-- create temp table for results
create temporary table if not exists __cust_size_report (
    customer text,
    provider_id text,
    report_month date,
    cluster_count bigint,
    node_count bigint,
    project_count bigint,
    pvc_count bigint,
    tag_count bigint
);
create index ix__cust_size_report on __cust_size_report (customer, provider_id, report_month);
-- loop construct
do $BODY$
declare
    schema_rec record;
    -- OCP data gather per-schema
    stmt_tmpl text = '
insert
  into __cust_size_report (
            customer,
            provider_id,
            report_month,
            cluster_count,
            node_count,
            project_count,
            pvc_count,
            tag_count
        )
select ''%1$s'' as "customer",
        rpp.provider_id as "provider_id",
        rpp.report_period_start::date as "report_month",
        count(distinct rpp.cluster_id) as "cluster_count",
        count(distinct n.node) as "node_count",
        count(distinct p.project) as "project_count",
        -- count(distinct ro.pod) as "pod_count",
        count(distinct pvc.persistent_volume_claim) as "pvc_count",
        max(rpml.tag_count) as "tag_count"
        -- count(*) as "raw_lineitem_count"
        -- starting with line item as we need the data ingestion counts
  from %1$s.reporting_ocpusagereportperiod rpp
  join %1$s.reporting_ocp_clusters c
    on rpp.cluster_id = c.cluster_id
  join %1$s.reporting_ocp_nodes n
    on c.uuid = n.cluster_id
  join %1$s.reporting_ocp_projects p
    on c.uuid = p.cluster_id
  join %1$s.reporting_ocp_pvcs pvc
    on c.uuid = pvc.cluster_id
        -- transformations to get tag counts
  join (
          select rpta.report_period_id,
                count(distinct rpta.tag) as "tag_count"
            from (
                  -- get the distinct tag (key + value) from pod and storage labels
                  -- summary is begin used here as it should only hold the data that
                  -- have already been filtered (if any filters exist)
                  select distinct
                          ruls.report_period_id,
                          key || ''|'' || uv.value as "tag"
                    from %1$s.reporting_ocpusagepodlabel_summary ruls
                    left join lateral (select unnest(ruls.values)) as uv(value)
                      on true
                    union
                  select distinct
                          rsls.report_period_id,
                          key || ''|'' || sv.value as "tag"
                    from %1$s.reporting_ocpstoragevolumelabel_summary rsls
                    left join lateral (select unnest(rsls.values)) as sv(value)
                      on true
                ) rpta(report_period_id, tag)
          group
              by rpta.report_period_id
        ) as rpml(report_period_id, tag_count)
    on rpml.report_period_id = rpp.id
  where rpp.report_period_start < ''%3$s''::timestamptz  -- start must be < end bounds as end bounds is start of next month
    and rpp.report_period_start >= ''%2$s''::timestamptz     -- end must be >= start bounds
  group
    by "customer",
        rpp."provider_id",
        "report_month";
';
begin
    for schema_rec in
        select distinct t.schema_name
          from public.api_tenant t
          join pg_namespace n
            on n.nspname = t.schema_name
          join public.api_customer c
            on c.schema_name = t.schema_name
          join public.api_provider p
            on p.customer_id = c.id
            and p."type" = any( (:provider_types) )
          where t.schema_name ~ '^acct'
            or t.schema_name ~ '^org'
          order
            by t.schema_name
    loop
        execute format(stmt_tmpl, schema_rec.schema_name, (:start_time), (:end_time));
    end loop;
end $BODY$ language plpgsql;
