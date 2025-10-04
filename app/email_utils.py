# app/email_utils.py
import os, requests

def send_email(to_email: str, subject: str, html: str):
    api_key = os.getenv("RESEND_API_KEY")
    sender  = os.getenv("SENDER_FROM", "onboarding@resend.dev")

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": sender,
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=12,
        )
        r.raise_for_status()
        print("[EMAIL] enviado com sucesso via Resend")
        return True
    except Exception as e:
        print(f"[EMAIL][ERROR] {e} - {r.text}")
        return False
