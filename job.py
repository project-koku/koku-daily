import logging
import sys

from kokudaily.config import Config
from kokudaily.config import REGISTRY
from kokudaily.reports import run_reports
from kokudaily.send import email
from kokudaily.send import prometheus
from kokudaily.send import redshift
from prometheus_client import push_to_gateway

root = logging.getLogger()
root.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
root.addHandler(handler)

LOG = logging.getLogger(__name__)

LOG.info("Starting report job.")

report_data = run_reports()

for target, report_dict in report_data.items():
    report_files = []
    recipients = Config.EMAIL_GROUPS.get(target)
    for report_name, report in report_dict.items():
        path = report.get("file")
        if path:
            report_files.append(path)
        prometheus(target, report_name, **report)
        redshift(target, report_name, **report)
    email(recipients, attachments=report_files, target=target)
    if Config.PROMETHEUS_PUSH_GATEWAY:
        push_to_gateway(
            Config.PROMETHEUS_PUSH_GATEWAY,
            job="cost_metrics",
            registry=REGISTRY,
        )

LOG.info("Completed report job.")
