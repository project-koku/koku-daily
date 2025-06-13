import logging
import sys

from kokudaily.config import Config
from kokudaily.config import REGISTRY
from kokudaily.reports import run_reports
from kokudaily.send import create_zip_archive
from kokudaily.send import email
from kokudaily.send import prometheus
from kokudaily.send import s3
from prometheus_client import push_to_gateway

root = logging.getLogger()
root.setLevel(Config.LOGLEVEL)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(Config.LOGLEVEL)
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
        s3(target, report_name, **report)
    zip_file_path = create_zip_archive(report_files, "koku_metrics.zip")
    if zip_file_path:
        LOG.info("Proceeding to email the compressed zip file.")
        email(recipients, attachments=[zip_file_path], target=target)
    else:
        LOG.error(
            "Skipping email because the zip archive could not be created."
        )

    if Config.PROMETHEUS_PUSH_GATEWAY:
        push_to_gateway(
            Config.PROMETHEUS_PUSH_GATEWAY,
            job="cost_metrics",
            registry=REGISTRY,
        )

LOG.info("Completed report job.")
