import smtplib
from engagement_course import config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(to_address, subject, message):
    msg = MIMEMultipart()
    msg['From'] = config.SMTP_USERNAME
    msg['To'] = to_address
    msg['Subject'] = subject
    msg.attach(MIMEText(message))
    mailserver = smtplib.SMTP(config.SMTP_HOSTNAME, config.SMTP_PORT)
    mailserver.ehlo()
    mailserver.starttls()
    mailserver.ehlo()
    mailserver.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
    mailserver.sendmail(config.SMTP_USERNAME, to_address, msg.as_string())
    mailserver.quit()