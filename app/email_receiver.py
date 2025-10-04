import os, imaplib, email, csv
from email.header import decode_header
from datetime import datetime
from pathlib import Path

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

EMAIL_USER = os.getenv("EMAIL_USER") or os.getenv("SMTP_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS") or os.getenv("SMTP_PASS")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LEADS_FILE = DATA_DIR / "leads.csv"

def _decode(s: str) -> str:
    if not s:
        return ""
    parts = decode_header(s)
    out = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", errors="replace")
        else:
            out += text
    return out

def _append_lead(row: dict):
    # Ensure CSV exists with header
    file_exists = LEADS_FILE.exists()
    with LEADS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp","from","subject","body"])
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def fetch_unread_to_leads(limit: int = 20) -> list[dict]:
    """
    Liga ao Gmail via IMAP e extrai os emails não lidos mais recentes para leads.csv.
    Retorna a lista de mensagens processadas (metadados).
    """
    if not EMAIL_USER or not EMAIL_PASS:
        raise RuntimeError("Definir EMAIL_USER e EMAIL_PASS nas variáveis de ambiente (.env).")

    processed = []
    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as M:
        M.login(EMAIL_USER, EMAIL_PASS)
        M.select("INBOX")
        status, data = M.search(None, '(UNSEEN)')
        if status != "OK":
            return []
        ids = data[0].split()
        # processar só os mais recentes até 'limit'
        ids = ids[-limit:]
        for num in ids:
            _, raw = M.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(raw[0][1])
            subject = _decode(msg.get("Subject", ""))
            from_ = _decode(msg.get("From", ""))
            body_text = ""

            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition", ""))
                    if ctype == "text/plain" and "attachment" not in disp:
                        payload = part.get_payload(decode=True) or b""
                        charset = part.get_content_charset() or "utf-8"
                        body_text = payload.decode(charset, errors="replace")
                        break
            else:
                payload = msg.get_payload(decode=True) or b""
                charset = msg.get_content_charset() or "utf-8"
                try:
                    body_text = payload.decode(charset, errors="replace")
                except Exception:
                    body_text = payload.decode("utf-8", errors="replace")

            row = {
                "timestamp": datetime.utcnow().isoformat(),
                "from": from_,
                "subject": subject,
                "body": body_text.strip(),
            }
            _append_lead(row)
            # Marcar como lido
            M.store(num, '+FLAGS', '\\Seen')
            processed.append({"from": from_, "subject": subject, "body_preview": body_text[:200]})
    return processed
