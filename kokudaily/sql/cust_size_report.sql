-- Get customer size information based on the data from the _setup.sql
select c.customer,
       c.provider_id,
       c.report_month,
       c.cluster_count,
       c.node_count,
       c.project_count,
       c.pod_count,
       c.tag_count,
       p.raw_lineitem_count as prev_month_lineitem_count,
       c.raw_lineitem_count as curr_month_lineitem_count,
       c.raw_lineitem_count - p.raw_lineitem_count as lineitem_change_count,
       round(c.raw_lineitem_count::numeric / coalesce(p.raw_lineitem_count, 0)::numeric, 4) as lineitem_change_pct
  from (
           -- current month view
           select m.customer,
                  m.provider_id,
                  max(m.report_month) as report_month,
                  max(m.cluster_count) as cluster_count,
                  max(m.node_count) as node_count,
                  max(m.project_count) as project_count,
                  max(m.pod_count) as pod_count,
                  max(m.tag_count) as tag_count,
                  max(m.raw_lineitem_count) as raw_lineitem_count
             from __cust_size_report m
            group
               by m.customer,
                  m.provider_id
       ) c
  left
  join lateral (
                   -- lateral join to get prior month's lineitem count (if available)
                   select lp.customer,
                          lp.provider_id,
                          max(lp.report_month) as report_month,
                          max(lp.raw_lineitem_count) as raw_lineitem_count
                     from __cust_size_report lp
                    where lp.customer = c.customer
                      and lp.provider_id = c.provider_id
                      and lp.report_month < c.report_month
                    group
                       by lp.customer,
                          lp.provider_id
               ) p
    on true;
