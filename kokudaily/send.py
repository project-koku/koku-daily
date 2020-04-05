import logging
import smtplib
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from kokudaily.config import Config


LOG = logging.getLogger(__name__)


def email(attachments=None, target=""):
    gmail_user = Config.EMAIL_USER
    gmail_password = Config.EMAIL_PASSWORD
    s = smtplib.SMTP("smtp.gmail.com:587")
    s.starttls()
    s.login(gmail_user, gmail_password)

    msg = MIMEMultipart()
    sender = gmail_user
    recipients = ["chambrid@redhat.com"]
    subject = (
        f"Cost Management {target.title()} Metrics Report: {Config.NAMESPACE}"
    )
    msg_text = "<p>See attached metrics.</p>"
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
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
