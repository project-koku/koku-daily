drop table if exists __cust_size_report;
-- create temp table for results
create temporary table if not exists __cust_size_report (
    customer text,
    provider_id text,
    report_month date,
    cluster_count bigint,
    node_count bigint,
    project_count bigint,
    pod_count bigint,
    tag_count bigint,
    raw_lineitem_count bigint
);
-- loop construct
do $BODY$
declare
    schema_rec record;
    stmt_tmpl text = '
insert
  into __cust_size_report (
            customer,
            provider_id,
            report_month,
            cluster_count,
            node_count,
            project_count,
            pod_count,
            tag_count,
            raw_lineitem_count
        )
select ''%1$s'' as "customer",
        rpp.provider_id as "provider_id",
        date_trunc(''month'', rp.interval_start)::date as "report_month",
        count(distinct rpp.cluster_id) as "cluster_count",
        count(distinct ro.node) as "node_count",
        count(distinct ro."namespace") as "project_count",
        count(distinct ro.pod) as "pod_count",
        max(rpml.tag_count) as "tag_count",
        count(*) as "raw_lineitem_count"
        -- starting with line item as we need the data ingestion counts
  from %1$s.reporting_ocpusagelineitem ro
        -- usage report has the usage bounds
  join %1$s.reporting_ocpusagereport rp
    on rp.id = ro.report_id
    and rp.interval_start < %(start_time)s::timestamptz  -- start must be < end bounds as end bounds is start of next month
    and rp.interval_end >= %(end_time)s::timestamptz     -- end must be >= start bounds
        -- report period has the provider and cluster
  join %1$s.reporting_ocpusagereportperiod rpp
    on rpp.id = ro.report_period_id
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
    on rpml.report_period_id = ro.report_period_id
  group
    by "customer",
        "provider_id",
        "report_month";
';
begin
    for schema_rec in
        select t.schema_name
          from public.api_tenant t
          join pg_namespace n
            on n.nspname = t.schema_name
          join public.api_customer c
            on c.schema_name = t.schema_name
          join public.api_provider p
            on p.customer_id = c.id
            and p."type" = any( %(provider_types)s )
          left
          join pg_catalog.pg_stat_user_tables psut
            on psut.schemaname = n.nspname
            and psut.relname = 'reporting_ocpusagelineitem'
          where t.schema_name like 'acct%'
          order
            by psut.n_live_tup desc
    loop
        execute format(stmt_tmpl, schema_rec.schema_name);
    end loop;
end $BODY$ language plpgsql;
