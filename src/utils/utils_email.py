"""Python module to send emails."""

# python modules
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Union


def send_email_with_attachment(
    sender_email,
    receiver_email,
    app_password,
    file_path: Union[Path, str, List[Union[Path, str]]],
    subject,
    body,
):
    """Send email with one or more attachments.

    Args:
        sender_email: Sender's email address
        receiver_email: Receiver's email address
        app_password: Gmail app password
        file_path: Single file path or list of file paths to attach
        subject: Email subject
        body: Email body text
    """
    # Create a multipart message
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    # Attach the body text
    msg.attach(MIMEText(body, "plain"))

    # Handle single file or list of files
    if not isinstance(file_path, list):
        file_paths = [file_path]
    else:
        file_paths = file_path

    # Attach each file
    for fp in file_paths:
        with open(fp, "rb") as file:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", f"attachment; filename={Path(fp).name}"
            )
            msg.attach(part)

    # Connect to Gmail's SMTP server and send the email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
