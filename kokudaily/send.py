import datetime
import logging
import smtplib
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
from kokudaily.config import Config
from kokudaily.config import REGISTRY
from kokudaily.engine import REDSHIFT_ENGINE
from kokudaily.reports import REPORTS
from prometheus_client import Gauge
from pytz import UTC
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table

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


def str_begins_or_ends_with(column_name, str_value):
    return column_name.startswith(str_value) or column_name.endswith(str_value)


def get_column_datatype(column_name):
    data_type = String(256)

    if str_begins_or_ends_with(
        column_name, "count"
    ) or str_begins_or_ends_with(column_name, "num"):
        data_type = Integer
    elif (
        str_begins_or_ends_with(column_name, "timestamp")
        or str_begins_or_ends_with(column_name, "date")
        or str_begins_or_ends_with(column_name, "datetime")
    ):
        data_type = DateTime

    return data_type


def create_table(engine, name, *cols):
    meta = MetaData()
    meta.reflect(bind=engine)
    if name in meta.tables:
        return

    table = Table(name, meta, *cols)
    table.create(engine)


def redshift(target, report_name, **report):
    if Config.REDSHIFT_HOST is None:
        return
    table_prefix = Config.REDSHIFT_TABLE_PREFIX
    table_name = f"{table_prefix}_{report_name}"

    LOG.info(f"Creating table={table_name} if it doesn't exist.")
    columns = []
    for col in report.get("columns"):
        col_obj = Column(col, get_column_datatype(col), nullable=True)
        columns.append(col_obj)
    columns.append(Column("record_datetime", DateTime, nullable=True))
    create_table(REDSHIFT_ENGINE, table_name, columns)

    today = datetime.datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC
    )

    df = pd.read_csv(report.get("file"))
    if df.empty:
        LOG.info(f"No data to insert into table={table_name}.")
        return

    LOG.info(f"Inserting data into table={table_name}.")
    df["record_datetime"] = today
    with REDSHIFT_ENGINE.connect() as con:
        df.to_sql(table_name, con=con, if_exists="append", index=False)
