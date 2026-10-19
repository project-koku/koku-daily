SELECT fc.account_id,
       cnr.provider_id,
       cnr.cluster_id,
       cnr.node,
       cnr.report_month,
       cnr.cpu_cores,
       cnr.memory_gigabytes,
       fc.org_id
  FROM __cust_node_report cnr
  JOIN __customers AS fc
    ON cnr.customer = fc.schema_name
WHERE fc.has_non_redhat = 1;
