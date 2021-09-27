import logging
import os
import smtplib
from datetime import date
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from tempfile import gettempdir

import pyarrow.parquet as pq
from kokudaily.config import Config
from kokudaily.config import REGISTRY
from kokudaily.reports import REPORTS
from minio import Minio
from prometheus_client import Gauge
from pyarrow import csv

LOG = logging.getLogger(__name__)


def email(recipients, attachments=None, target=""):
    if recipients is None:
        return
    gmail_user = Config.EMAIL_USER
    gmail_password = Config.EMAIL_PASSWORD
    s = smtplib.SMTP("smtp.gmail.com:587")
    s.starttls()
    s.login(gmail_user, gmail_password)

    msg = MIMEMultipart()
    sender = gmail_user
    subject = (
        f"Cost Management {target.title()} Metrics Report: {Config.NAMESPACE}"
    )
    msg_text = "<p>See attached metrics.</p>"
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipients
    if attachments is not None:
        for each_file_path in attachments:
            try:
                file_name = each_file_path.split("/")[-1]
                part = MIMEBase("application", "octet-stream")
                part.set_payload(open(each_file_path, "rb").read())

                encode_base64(part)
                part.add_header(
                    "Content-Disposition", "attachment", filename=file_name
                )
                msg.attach(part)
            except:  # noqa: E722
                LOG.error("Could not attach file.")
    msg.attach(MIMEText(msg_text, "html"))
    s.sendmail(sender, recipients, msg.as_string())
    LOG.info(
        f"Sending email {subject} with files {attachments} to {recipients}."
    )


def prometheus(target, report_name, **report):
    metric_name = f"hccm_{report_name}"
    metric_config = REPORTS.get(report_name, {}).get("prometheus")
    if Config.PROMETHEUS_PUSH_GATEWAY and metric_config:
        LOG.info(f"Gathering metric for {metric_name} of target {target}.")
        data_dicts = report.get("data_dicts", [])
        if data_dicts:
            value_key = metric_config.get("value")
            labels = metric_config.get("labels", [])
            labels.append("namespace")
            for idx, data_dict in enumerate(data_dicts):
                value = data_dict.get(value_key)
                if labels:
                    if idx == 0:
                        gauge = Gauge(
                            name=metric_name,
                            documentation=report_name,
                            registry=REGISTRY,
                            labelnames=labels,
                        )
                    gauge_labels = {}
                    for label in labels:
                        if label == "namespace":
                            label_value = Config.NAMESPACE
                        else:
                            label_value = data_dict.get(label)
                        if label_value is not None:
                            gauge_labels[label] = str(label_value)
                    LOG.info(
                        f"Setting gauge {metric_name} with labels {labels}"
                        f" with {gauge_labels} and value {value}."
                    )
                    gauge.labels(**gauge_labels).set(int(value))
        else:
            LOG.warning(f"No captured metric data found for {metric_name}.")
    else:
        LOG.info(f"No metric recorded for {metric_name} of target {target}.")


def get_minio_client():
    """Create client for handling object store interaction."""
    minio_client = Minio(
        Config.MINIO_ENDPOINT,
        access_key=Config.MINIO_ACCESS_KEY,
        secret_key=Config.MINIO_SECRET_KEY,
        secure=Config.MINIO_SECURE,
    )
    return minio_client


def s3(target, report_name, **report):
    if not Config.MINIO_ACCESS_KEY:
        return

    minio_client = get_minio_client()
    bucket_exists = minio_client.bucket_exists(bucket_name=Config.MINIO_BUCKET)
    if not bucket_exists:
        LOG.info(
            f"{Config.MINIO_BUCKET} doesn't exits, so data cannot be uploaded."
        )

    table = csv.read_csv(report.get("file"))

    tmp = gettempdir()
    temp_dir = os.path.join(tmp, "parquet_reports")
    os.makedirs(temp_dir, exist_ok=True)
    tempfile = os.path.join(temp_dir, f"{report_name}.parquet")
    pq.write_table(table, tempfile)

    todays_date = date.today()
    metric_file_name = f"{Config.WAREHOUSE_PATH}/metric={report_name}/year={todays_date.year}/month={todays_date.month}/day={todays_date.day}/{report_name}.parquet"  # noqa

    LOG.info(
        f"Uploading metric file {metric_file_name} to {Config.MINIO_BUCKET}."
    )
    minio_client.fput_object(
        bucket_name=Config.MINIO_BUCKET,
        object_name=metric_file_name,
        file_path=tempfile,
    )
