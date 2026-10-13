INSERT
  INTO __cust_cost_model_report (
      customer,
      cost_model_id,
      source_type,
      created_timestamp,
      updated_timestamp,
      rates,
      markup,
      distribution,
      cost_model_map_id,
      provider_id,
      cluster_id
  )
SELECT    :customer AS "customer",
          cm.uuid AS "cost_model_id",
          cm.source_type AS "source_type",
          cm.created_timestamp AS "created_timestamp",
          cm.updated_timestamp AS "updated_timestamp",
          cm.rates AS "rates",
          cm.markup AS "markup",
          cm.distribution AS "distribution",
          map.cost_model_id AS "cost_model_map_id",
          p.uuid AS "provider_id",
          auth.credentials->>'cluster_id' AS "cluster_id"
FROM      {schema}.cost_model cm
          -- use left join for provider mapping to keep unused cost models
LEFT JOIN {schema}.cost_model_map map
ON        map.cost_model_id = cm.uuid
JOIN      public.api_provider p
ON        p.uuid = map.provider_uuid
          -- cluster ids (if applicable) can be read from auth credentials
JOIN      public.api_providerauthentication auth
ON        auth.id = p.authentication_id;
