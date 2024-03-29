from datetime import datetime
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.header import Header
from flask import render_template, current_app
from app.constants import HighLevelPolicyType
from app.models.database_model import DeviceTypePolicy
from app.monitors.pihole_monitor import weekly_summary
from app.reporting.pihole_reports import figure_to_byte_img, create_stacked_bar_chart, create_pie_chart
from app.models import User, Device, RoomPolicy
from app.extensions import db
from typing import Union


class EmailBuilder:
    def __init__(self):
        self.msg = MIMEMultipart('related')

    def with_subject(self, subject):
        self.msg['Subject'] = Header(subject, 'utf-8')
        return self

    def with_sender(self, sender):
        self.msg['From'] = sender
        return self

    def with_recipient(self, recipient):
        self.msg['To'] = recipient
        return self

    def with_html_content(self, html_content):
        self.msg.attach(MIMEText(html_content, 'html'))
        return self

    def with_text_content(self, text_content):
        self.msg.attach(MIMEText(text_content, 'plain'))
        return self

    def add_image(self, image: MIMEImage, content_id: str | None):
        if content_id is not None:
            image.add_header('Content-ID', f'<{content_id}>')
        self.msg.attach(image)
        return self

    def build(self):
        return self.msg


def create_weekly_email(user: User) -> MIMEMultipart:
    recipient = user.email_address
    username = user.username

    text_content = "Your email client does not support HTML messages. " \
                   "Please use an email client that does."

    # Get the weekly summary from pihole monitor
    df = weekly_summary()
    top_domains = df[['client_name', "domain"]].value_counts().nlargest(10).sort_values(ascending=False)
    top_dict = top_domains.to_dict()

    html_content = render_template('emails/weekly-summary.html', username=username, top_dict=top_dict)

    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    img_path = os.path.join(basedir, 'static', 'assets', 'logo.png')
    with open(img_path, "rb") as img_file:
        enc_img = img_file.read()

    img_1 = figure_to_byte_img(create_pie_chart(df))
    img_2 = figure_to_byte_img(create_stacked_bar_chart(df))

    logo = MIMEImage(enc_img, 'png')
    chart1 = MIMEImage(img_1, 'png')
    chart2 = MIMEImage(img_2, 'png')

    msg = EmailBuilder() \
        .with_subject('Weekly summary') \
        .with_sender(current_app.config["MAIL_USERNAME"]) \
        .with_recipient(recipient) \
        .with_html_content(html_content) \
        .with_text_content(text_content) \
        .add_image(logo, "logo") \
        .add_image(chart1, "chart1") \
        .add_image(chart2, "chart2") \
        .build()

    return msg


def create_threshold_notification_mail(user:User, policy: Union[RoomPolicy,DeviceTypePolicy], device: Device)->MIMEMultipart:
    recipient = user.email_address
    username = user.username
    print("Warning. The device", device.device_name ," surpassed the request threshold defined in policy ", policy.name ,".")
    # text_content = str("Warning. The device", device.device_name ," surpassed the request threshold defined in policy ", room_policy.name ,".")
    text_content="Test the mail"
    #-----------------only for testing
     # Get the weekly summary from pihole monitor
    df = weekly_summary()
    top_domains = df[['client_name', "domain"]].value_counts().nlargest(10).sort_values(ascending=False)
    top_dict = top_domains.to_dict()
    date_time = datetime.now().time().strftime("%H:%M:%S")



    html_content = render_template('emails/threshold-violation.html', username=username, date_time=date_time, device=device, policy=policy, top_dict=top_dict)
    #-----------------
    msg = EmailBuilder() \
        .with_subject('Request Threshold Violation') \
        .with_sender(current_app.config["MAIL_USERNAME"]) \
        .with_recipient(recipient) \
        .with_html_content(html_content) \
        .with_text_content(text_content) \
        .build()
    return msg

def send_weekly_emails():
    for msg in generate_weekly_emails():
        send_email(msg)

def send_threshold_notification_mail(policy: Union[RoomPolicy, DeviceTypePolicy],device: Device):
    users = db.session.execute(db.select(User).where(User.email_address != None)).scalars().all() 
    for user in users:
        print("email address:", user.email_address)
        msg = create_threshold_notification_mail(user, policy, device)
        send_email(msg)


def generate_weekly_emails():
    users = db.session.execute(db.select(User).where(User.email_address != None)).scalars().all()  # noqa
    
    for user in users:
        msg = create_weekly_email(user)
        yield msg


def send_email(msg: MIMEMultipart):
    try:
        with smtplib.SMTP(current_app.config["MAIL_SERVER"], current_app.config["MAIL_PORT"]) as smtp:
            smtp.starttls()
            smtp.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
            smtp.send_message(msg)
    except smtplib.SMTPException as e:
        current_app.logger.error(f'Email not sent to {msg["To"]}. \n Error: {e}')

    current_app.logger.debug(f'Email sent to {msg["To"]}')
    return 'Sent'



