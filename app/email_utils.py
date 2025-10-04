from dotenv import load_dotenv
load_dotenv(); load_dotenv(".env.txt")

import os, smtplib
from email.message import EmailMessage

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_TO   = os.getenv("SMTP_TO")  # default recipient
SMTP_SECURE = os.getenv('SMTP_SECURE', '').lower()  # '', 'ssl', 'starttls'

def send_order_email(subject: str, body: str, to: str | None = None) -> bool:
    """
    Sends an email via SMTP if environment variables are configured.
    Returns True if sent, False if skipped or failed.
    """
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, (to or SMTP_TO)]):
        # Missing config, skip silently
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to or SMTP_TO
    msg.set_content(body)

    try:
        if SMTP_PORT == 465 or SMTP_SECURE == 'ssl':
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        return True
    except Exception:
        return False
