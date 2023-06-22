DROP TABLE IF EXISTS __cust_cost_model_report;
-- create temp table for results
CREATE TEMPORARY TABLE IF NOT EXISTS __cust_cost_model_report (
    customer text,
    cost_model_id text,
    source_type text,
    created_timestamp date,
    updated_timestamp date,
    rates jsonb,
    markup jsonb,
    distribution text,
    cost_model_map_id text,
    provider_id text,
    cluster_id text
);
-- loop construct
DO $BODY$
DECLARE
    schema_rec record;
    -- OCP data gather per-schema
    stmt_tmpl text = '
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
SELECT    ''%%1$s'' AS "customer",
          cm.uuid AS "cost_model_id",
          cm.source_type AS "source_type",
          cm.created_timestamp AS "created_timestamp",
          cm.updated_timestamp AS "updated_timestamp",
          cm.rates AS "rates",
          cm.markup AS "markup",
          cm.distribution AS "distribution",
          map.cost_model_id AS "cost_model_map_id",
          p.uuid AS "provider_id",
          auth.credentials->>''cluster_id'' AS "cluster_id"
FROM      %%1$s.cost_model cm
          -- use left join for provider mapping to keep unused cost models
LEFT JOIN %%1$s.cost_model_map map
ON        map.cost_model_id = cm.uuid
JOIN      public.api_provider p
ON        p.uuid = map.provider_uuid
          -- cluster ids (if applicable) can be read from auth credentials
JOIN      public.api_providerauthentication auth
ON        auth.id = p.authentication_id;
';
BEGIN
    FOR schema_rec IN
        SELECT DISTINCT t.schema_name
        FROM   public.api_tenant t
        JOIN   pg_namespace n
        ON     n.nspname = t.schema_name
        JOIN   public.api_customer c
        ON     c.schema_name = t.schema_name
        WHERE  t.schema_name ~ '^acct'
        OR     t.schema_name ~ '^org'
        ORDER
           BY  t.schema_name
    LOOP
        EXECUTE format(stmt_tmpl, schema_rec.schema_name);
    END LOOP;
END $BODY$ LANGUAGE plpgsql;
