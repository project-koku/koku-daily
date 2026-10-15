CREATE TABLE IF NOT EXISTS public.api_tenant (schema_name text);
CREATE TABLE IF NOT EXISTS public.api_customer (id integer PRIMARY KEY, account_id text, org_id text, schema_name text);
CREATE TABLE IF NOT EXISTS public.api_user (id integer, customer_id integer, email text);
CREATE TABLE IF NOT EXISTS public.api_provider (uuid uuid PRIMARY KEY, customer_id integer, type text, authentication_id integer, infrastructure_id integer, setup_complete boolean, created_timestamp timestamptz, data_updated_timestamp timestamptz, name text);
CREATE TABLE IF NOT EXISTS public.api_providerauthentication (id integer, credentials jsonb);
CREATE TABLE IF NOT EXISTS public.api_providerinfrastructuremap (id integer, infrastructure_type text);
CREATE TABLE IF NOT EXISTS public.api_sources (koku_uuid text, account_id text, source_id integer, name text, source_uuid uuid, source_type text, status jsonb, org_id text);
CREATE TABLE IF NOT EXISTS public.api_exchangerates (currency_type text, exchange_rate numeric);
CREATE TABLE IF NOT EXISTS public.reporting_common_costusagereportmanifest (id integer, provider_id uuid, completed_datetime timestamptz, creation_datetime timestamptz, billing_period_start_datetime timestamptz, assembly_id text, operator_airgapped boolean, operator_certified boolean, operator_version text, operator_type text, cluster_id text);
CREATE TABLE IF NOT EXISTS public.reporting_common_costusagereportstatus (manifest_id integer, completed_datetime timestamptz);
TRUNCATE public.api_tenant, public.api_customer, public.api_user, public.api_provider, public.api_providerauthentication, public.api_exchangerates, public.api_sources, public.api_providerinfrastructuremap, public.reporting_common_costusagereportmanifest, public.reporting_common_costusagereportstatus;
INSERT INTO public.api_customer VALUES (1,'10001','1','org1'),(2,'10002','2','org2'),(3,'internal','3','acct6193296'),(4,NULL,'11789772','orgempty');
INSERT INTO public.api_tenant SELECT schema_name FROM public.api_customer;
ALTER TABLE public.api_tenant ADD COLUMN IF NOT EXISTS id integer;
UPDATE public.api_tenant t SET id = c.id FROM public.api_customer c WHERE c.schema_name=t.schema_name;
ALTER TABLE public.reporting_common_costusagereportmanifest ADD COLUMN IF NOT EXISTS operator_errors integer;
INSERT INTO public.api_user VALUES (1,1,'one@example.com'),(2,2,'two@example.org'),(3,3,'internal@redhat.com'),(4,4,'excluded@example.com');
ALTER TABLE public.api_user ADD COLUMN IF NOT EXISTS username text;
UPDATE public.api_user SET username = email;
INSERT INTO public.api_providerauthentication VALUES (1,'{"cluster_id":"cluster1"}');
INSERT INTO public.api_providerinfrastructuremap VALUES (1,'AWS');
INSERT INTO public.api_provider SELECT ('00000000-0000-0000-0000-00000000000'||id)::uuid,id,'OCP',1,1,true,now()-interval '2 days',now(),'test' FROM public.api_customer;
INSERT INTO public.api_sources SELECT uuid::text,'10001',customer_id,'test',uuid,type,'{}',customer_id::text FROM public.api_provider;
INSERT INTO public.api_exchangerates VALUES ('USD',1),('EUR',2);
INSERT INTO public.reporting_common_costusagereportmanifest SELECT customer_id,uuid,now(),now(),date_trunc('month',now()),'assembly',false,true,'1.0','community','cluster1' FROM public.api_provider;
DO $$
DECLARE s text;
BEGIN
FOR s IN SELECT schema_name FROM public.api_tenant LOOP
EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE',s);
EXECUTE format('CREATE SCHEMA %I',s);
EXECUTE format('CREATE TABLE %I.cost_model (uuid uuid, source_type text, created_timestamp timestamptz, updated_timestamp timestamptz, rates jsonb, markup jsonb, distribution text, currency text)',s);
EXECUTE format('CREATE TABLE %I.cost_model_map (cost_model_id uuid, provider_uuid uuid)',s);
EXECUTE format('CREATE TABLE %I.reporting_ocpusagereportperiod (id integer, provider_id uuid, cluster_id text, report_period_start date)',s);
EXECUTE format('CREATE TABLE %I.reporting_ocpusagelineitem_daily_summary (report_period_id integer, node text, node_capacity_cpu_cores numeric, node_capacity_memory_gigabytes numeric, usage_start date)',s);
EXECUTE format('CREATE TABLE %I.reporting_aws_cost_summary_p (usage_start date, unblended_cost numeric, calculated_amortized_cost numeric, currency_code text)',s);
EXECUTE format('CREATE TABLE %I.reporting_azure_cost_summary_p (usage_start date, pretax_cost numeric, currency text)',s);
EXECUTE format('CREATE TABLE %I.reporting_gcp_cost_summary_p (usage_start date, unblended_cost numeric, credit_amount numeric, currency text)',s);
EXECUTE format('CREATE TABLE %I.reporting_ocp_cost_summary_p (usage_start date, infrastructure_raw_cost numeric, raw_currency text, cost_model_cpu_cost numeric, cost_model_memory_cost numeric, cost_model_volume_cost numeric, source_uuid uuid, cost_model_rate_type text)',s);
EXECUTE format('CREATE TABLE %I.reporting_ocp_nodes (node text, node_role text, architecture text)',s);
EXECUTE format('CREATE TABLE %I.reporting_ocp_pod_summary_by_node_p (node text, node_capacity_cpu_cores numeric, node_capacity_memory_gigabytes numeric, usage_start date, cluster_id text, cluster_capacity_cpu_core_hours numeric, cluster_capacity_memory_gigabyte_hours numeric, cost_model_rate_type text)',s);
EXECUTE format('CREATE TABLE %I.reporting_ocp_volume_summary_p (usage_start date, cluster_id text, persistentvolumeclaim text, volume_request_storage_gigabyte_months numeric, persistentvolumeclaim_capacity_gigabyte_months numeric, cost_model_rate_type text)',s);
EXECUTE format('CREATE TABLE %I.reporting_ocptags_values (key text)',s);
EXECUTE format('CREATE TABLE %I.reporting_awstags_values (key text)',s);
EXECUTE format('CREATE TABLE %I.reporting_azuretags_values (key text)',s);
EXECUTE format('CREATE TABLE %I.reporting_gcptags_values (key text)',s);
IF s != 'orgempty' THEN
EXECUTE format('INSERT INTO %I.cost_model VALUES (''10000000-0000-0000-0000-000000000001'',''OCP'',now(),now(),''[{"tag_rates": {"x": 1.25}}]'',''{}'',''cpu'',''USD''),(''10000000-0000-0000-0000-000000000002'',''AWS'',now(),now(),''[]'',''{"value":1}'',''memory'',''EUR'')',s);
EXECUTE format('INSERT INTO %I.cost_model_map SELECT ''10000000-0000-0000-0000-000000000001'',uuid FROM public.api_provider WHERE customer_id=1',s);
EXECUTE format('INSERT INTO %I.reporting_ocptags_values VALUES (''a''),(''a''),(''b'')',s);
EXECUTE format('INSERT INTO %I.reporting_awstags_values VALUES (''x'')',s);
EXECUTE format('INSERT INTO %I.reporting_ocpusagereportperiod VALUES (1,''00000000-0000-0000-0000-000000000001'',''cluster1'',date_trunc(''month'',now()))',s);
EXECUTE format('INSERT INTO %I.reporting_ocpusagelineitem_daily_summary VALUES (1,''node1'',1.6,4.4,current_date),(1,''node1'',1.5,4.3,current_date)',s);
EXECUTE format('INSERT INTO %I.reporting_aws_cost_summary_p VALUES (current_date,0.005,3.14159,''USD''),(current_date,2.555,4.555,''EUR'')',s);
EXECUTE format('INSERT INTO %I.reporting_azure_cost_summary_p VALUES (current_date,10.005,''EUR'')',s);
EXECUTE format('INSERT INTO %I.reporting_gcp_cost_summary_p VALUES (current_date,20.555,-1.115,''USD'')',s);
EXECUTE format('INSERT INTO %I.reporting_ocp_cost_summary_p VALUES (current_date,100.005,''EUR'',1.115,2.225,3.335,''00000000-0000-0000-0000-000000000001'',''Infrastructure''),(current_date,0,''USD'',2,3,4,''00000000-0000-0000-0000-000000000001'',''Supplementary'')',s);
EXECUTE format('INSERT INTO %I.reporting_ocp_nodes VALUES (''node1'',''worker'',''x86_64''),(''node2'',''master'',''arm64'')',s);
EXECUTE format('INSERT INTO %I.reporting_ocp_pod_summary_by_node_p VALUES (''node1'',4,16,current_date,''cluster1'',96,384,NULL),(''node2'',2,8,current_date,''cluster1'',48,192,NULL)',s);
EXECUTE format('INSERT INTO %I.reporting_ocp_volume_summary_p VALUES (current_date,''cluster1'',''pvc1'',0.25,0.5,NULL)',s);
END IF;
END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS public.__customer_total_data (
date date PRIMARY KEY,
total_aws_unblended_cost numeric(33,2),
total_aws_calculated_amortized_cost numeric(33,2),
total_azure_pretax_cost numeric(33,2),
total_gcp_unblended_cost numeric(33,2),
total_gcp_total numeric(33,2),
total_total_infrastructure_raw_cost numeric(33,2),
total_total_cost_model_costs numeric(33,2),
total_infra_total_cost_model numeric(33,2),
total_infra_cost_model_cpu_cost numeric(33,2),
total_infra_cost_model_memory_cost numeric(33,2),
total_infra_cost_model_volume_cost numeric(33,2),
total_sup_total_cost_model numeric(33,2),
total_sup_cost_model_cpu_cost numeric(33,2),
total_sup_cost_model_memory_cost numeric(33,2),
total_sup_cost_model_volume_cost numeric(33,2),
total_cluster_count bigint,
total_node_count bigint,
total_infra_node_count bigint,
total_control_plane_node_count bigint,
total_worker_node_count bigint,
total_infra_node_cpu_cores numeric(33,2),
total_control_plane_node_cpu_cores numeric(33,2),
total_worker_node_cpu_cores numeric(33,2),
total_infra_node_mem_gb numeric(33,2),
total_control_plane_node_mem_gb numeric(33,2),
total_worker_node_mem_gb numeric(33,2),
total_pvc_count bigint,
total_cluster_capacity_cores numeric(33,2),
total_cluster_capacity_core_hours numeric(33,2),
total_cluster_capacity_memory_gb numeric(33,2),
total_cluster_capacity_memory_gb_hours numeric(33,2),
total_volume_request_gb numeric(33,2),
total_volume_request_gb_mo numeric(33,2),
total_pvc_capacity_gb numeric(33,2),
total_pvc_capacity_gb_mo numeric(33,2)
);
TRUNCATE public.__customer_total_data;
INSERT INTO public.__customer_total_data (date,total_aws_unblended_cost) VALUES (DATE '2020-01-01', 123.45);
