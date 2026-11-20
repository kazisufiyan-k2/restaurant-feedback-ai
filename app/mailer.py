"""
SMTP mailer (works with common SMTP providers).

Environment variables:
  SMTP_HOST, SMTP_PORT (587 or 465), SMTP_USER, SMTP_PASSWORD, MAIL_FROM, MAIL_REPLY_TO (optional)
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr


def smtp_configured() -> bool:
    return all(os.getenv(k) for k in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"])


def send_mail(to: str, subject: str, text: str, html: str = None) -> None:
    if not smtp_configured():
        raise RuntimeError("SMTP is not configured")
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    name, addr = parseaddr(os.getenv("MAIL_FROM") or user)

    msg = EmailMessage()
    msg["From"] = formataddr((name, addr or user))
    msg["To"] = to
    msg["Subject"] = subject
    if os.getenv("MAIL_REPLY_TO"):
        msg["Reply-To"] = os.getenv("MAIL_REPLY_TO")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)