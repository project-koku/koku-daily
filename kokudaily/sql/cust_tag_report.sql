-- Get customer tag information based on the data from the _setup.sql
select customer,
       openshift_label_key_count,
       aws_tag_key_count,
       azure_tag_key_count,
       gcp_label_key_count
from __cust_tag_report
;