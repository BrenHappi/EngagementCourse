import smtplib
from flask import current_app
from engagement_course import config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(to_address, subject, message) -> bool:
    """Sends an email. Never raises: a mail failure must not break the user action."""
    msg = MIMEMultipart()
    msg['From'] = config.SMTP_USERNAME
    msg['To'] = to_address
    msg['Subject'] = subject
    msg.attach(MIMEText(message))
    try:
        with smtplib.SMTP(config.SMTP_HOSTNAME, config.SMTP_PORT, timeout=config.SMTP_TIMEOUT) as mailserver:
            mailserver.starttls()
            mailserver.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            mailserver.sendmail(config.SMTP_USERNAME, to_address, msg.as_string())
    except (smtplib.SMTPException, OSError):
        current_app.logger.exception("Failed to send email to %s", to_address)
        return False
    return True
