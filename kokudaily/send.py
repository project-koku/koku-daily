import logging
import os
import smtplib
import zipfile
from datetime import date
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pyarrow as pa
import pyarrow.compute as pc
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
                    try:
                        gauge.labels(**gauge_labels).set(int(value))
                    except ValueError as ve:
                        LOG.error(ve, exc_info=True)
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


def _csv_candidates(column, candidates):
    if not candidates:
        return []
    # Reuse Arrow's CSV converters, including their whitespace,
    # boolean and time parsing rules, on one bounded column batch.
    sink = pa.BufferOutputStream()
    csv.write_csv(pa.table({"value": column}), sink)
    buffer = sink.getvalue()
    read_options = csv.ReadOptions(use_threads=False)
    inferred = (
        csv.read_csv(pa.BufferReader(buffer), read_options=read_options)
        .schema.field(0)
        .type
    )
    valid = []
    for kind in candidates:
        if pa.types.is_timestamp(kind) and not pa.types.is_null(inferred):
            zoned = pa.types.is_timestamp(inferred) and bool(inferred.tz)
            if bool(kind.tz) != zoned:
                continue
        try:
            csv.read_csv(
                pa.BufferReader(buffer),
                read_options=read_options,
                convert_options=csv.ConvertOptions(
                    column_types={"value": kind}
                ),
            )
        except pa.ArrowInvalid:
            continue
        valid.append(kind)
    return valid


def _parquet_types(path):
    """Infer across the entire CSV with bounded batches before writing Parquet.

    Arrow's streaming reader freezes types after its first block. Track the
    documented inference candidates across all blocks so late non-null values
    and numeric promotion retain the previous TableReader schema.
    """
    with csv.open_csv(path) as header:
        names = header.schema.names
    kinds = [
        pa.int64(),
        pa.bool_(),
        pa.date32(),
        pa.time32("s"),
        pa.timestamp("s"),
        pa.timestamp("ns"),
        pa.timestamp("s", "UTC"),
        pa.timestamp("ns", "UTC"),
        pa.float64(),
    ]
    candidates = {name: list(kinds) for name in names}
    present = {name: False for name in names}
    options = csv.ConvertOptions(
        column_types={name: pa.string() for name in names}
    )
    nulls = pa.array(options.null_values)
    with csv.open_csv(path, convert_options=options) as batches:
        for batch in batches:
            for name, column in zip(names, batch.columns):
                values = pc.if_else(
                    pc.is_in(column, value_set=nulls), None, column
                )
                present[name] = present[name] or values.null_count < len(
                    values
                )
                candidates[name] = _csv_candidates(column, candidates[name])
    return {
        name: (candidates[name][0] if candidates[name] else pa.string())
        if present[name]
        else pa.null()
        for name in names
    }


def s3(target, report_name, **report):
    if not Config.MINIO_ACCESS_KEY:
        return

    minio_client = get_minio_client()
    bucket_exists = minio_client.bucket_exists(bucket_name=Config.MINIO_BUCKET)
    if not bucket_exists:
        LOG.info(
            f"{Config.MINIO_BUCKET} doesn't exits, so data cannot be uploaded."
        )

    # Keep conversion memory bounded and scratch beside the source CSV.
    temp_dir = os.path.dirname(report["file"])
    parquet_path = os.path.join(temp_dir, f"{report_name}.parquet")
    options = csv.ConvertOptions(column_types=_parquet_types(report["file"]))
    with csv.open_csv(report["file"], convert_options=options) as batches:
        with pq.ParquetWriter(parquet_path, batches.schema) as writer:
            for batch in batches:
                writer.write_batch(batch)

    todays_date = date.today()
    metric_file_name = f"{Config.WAREHOUSE_PATH}/metric={report_name}/year={todays_date.year}/month={todays_date.month}/day={todays_date.day}/{report_name}.parquet"  # noqa

    LOG.info(
        f"Uploading metric file {metric_file_name} to {Config.MINIO_BUCKET}."
    )
    minio_client.fput_object(
        bucket_name=Config.MINIO_BUCKET,
        object_name=metric_file_name,
        file_path=parquet_path,
    )


def create_zip_archive(files_to_zip, zip_filename):
    """
    Creates a compressed zip archive from a list of files.

    Args:
        files_to_zip (list): A list of full paths to the files to be included.
        zip_filename (str): Name for the output zip file "metrics_report.zip".

    Returns:
        str: The full path to the newly created zip archive, or None if error occurs.  # noqa
    """
    if not files_to_zip:
        LOG.warning("No files provided to zip.")
        return None
    try:
        zip_filepath = os.path.join(
            os.path.dirname(files_to_zip[0]), zip_filename
        )
        LOG.info(f"Creating zip archive at: {zip_filepath}")
        with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_zip:
                # Use os.path.basename to avoid full directory structure in the zip  # noqa
                csv_name = os.path.basename(file_path)
                zipf.write(file_path, csv_name)
                LOG.info(f"Added {csv_name} to zip.")
        return zip_filepath
    except Exception as e:
        LOG.error(f"Failed to create zip archive: {e}")
        return None
