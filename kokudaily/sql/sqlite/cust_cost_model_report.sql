SELECT fc.account_id,
       cmr.cost_model_id,
       cmr.source_type,
       cmr.created_timestamp,
       cmr.updated_timestamp,
       cmr.provider_id,
       cmr.cluster_id,
       fc.org_id
  FROM __cust_cost_model_report cmr
  JOIN __customers AS fc
    ON fc.schema_name = cmr.customer
WHERE fc.has_non_redhat = 1;
