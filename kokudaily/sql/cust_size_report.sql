-- Get customer size information based on the data from the _setup.sql
select c.customer,
       c.provider_id,
       c.report_month,
       c.cluster_count,
       c.node_count,
       c.project_count,
       c.pvc_count,
       c.tag_count
  from (
           -- current month view
           select m.customer,
                  m.provider_id,
                  max(m.report_month) as report_month,
                  max(m.cluster_count) as cluster_count,
                  max(m.node_count) as node_count,
                  max(m.project_count) as project_count,
                  max(m.pvc_count) as pvc_count,
                  max(m.tag_count) as tag_count
             from __cust_size_report m
            group
               by m.customer,
                  m.provider_id
       ) c
;
