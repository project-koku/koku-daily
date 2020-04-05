import logging
import sys

from kokudaily.reports import run_reports
from kokudaily.send import email

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
LOG.info(report_data)

for target, report_dict in report_data.items():
    report_files = []
    for report in report_dict.values():
        path = report.get("file")
        if path:
            report_files.append(path)
    email(attachments=report_files, target=target)

LOG.info("Completed report job.")
