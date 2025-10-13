from dotenv import load_dotenv
load_dotenv(override=True)
load_dotenv(".env.txt", override=True)

import csv, smtplib
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
import csv, smtplib
from email.message import EmailMessage
from datetime import datetime
import os, math, re, requests
from fastapi import FastAPI, Request, Form
from . import email_receiver
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List
from pathlib import Path
import csv, smtplib
from email.message import EmailMessage
from datetime import datetime
from app.service_catalog import CATALOG, get_item

TRAVEL_RATE_EUR_PER_KM = float(os.getenv('PRICE_PER_KM', '0.66'))
COMPANY_LAT = float(os.getenv("COMPANY_LAT", "0"))
COMPANY_LNG = float(os.getenv("COMPANY_LNG", "0"))
OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")  # optional

# Hourly rates per category
CATEGORY_RATES = {
    "Limpeza Geral": 20.0,
    "Limpeza Profunda": 25.0,
    "Limpeza Especial": 30.0,
}

# Typology hours
TYPOLOGY_HOURS = {
    "T1": 1,
    "T2": 2,
    "T3": 3,
    "T4": 4,
    "T5": 5,
}


# --- Email/CSV config (opcional) ---
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
NOTIFY_TO = os.getenv("NOTIFY_TO")
SENDER_FROM = os.getenv("SENDER_FROM", SMTP_USER or "no-reply@example.com")
SMTP_SECURE = os.getenv('SMTP_SECURE', '').lower()  # '', 'ssl', 'starttls'

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LEADS_CSV = DATA_DIR / "leads.csv"

app = FastAPI(title="Cleaning Services Quote")
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "catalog": CATALOG})

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calc_service_cost(selected_categories: List[str], typology: str) -> float:
    hours = TYPOLOGY_HOURS.get(typology, 0)
    total = 0.0
    for cat in selected_categories:
        rate = CATEGORY_RATES.get(cat, 0.0)
        total += rate * hours
    return total

@app.post("/quote")
async def quote(request: Request, categories: List[str] = Form(default=[])):
    if not categories:
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": "Selecione pelo menos um tipo de limpeza."}
        )

    selected_labels = []
    for cat in categories:
        items = CATALOG.get(cat, [])
        selected_labels.append({"category": cat, "items": [it.label for it in items]})
    return templates.TemplateResponse("quote.html", {
        "request": request,
        "selected": selected_labels,
        "category_rates_json": __import__("json").dumps(CATEGORY_RATES),
        "typology_hours_json": __import__("json").dumps(TYPOLOGY_HOURS)
    })

@app.post("/api/estimate")
async def api_estimate(
    categories: List[str] = Form(default=[]),
    typology: str = Form(...),
    client_lat: float = Form(...),
    client_lng: float = Form(...),
):
    if COMPANY_LAT == 0 and COMPANY_LNG == 0:
        return JSONResponse(
            {"ok": False, "error": "Defina COMPANY_LAT e COMPANY_LNG nas variáveis de ambiente."},
            status_code=400
        )

    # validação básica das coordenadas
    if not (-90.0 <= client_lat <= 90.0 and -180.0 <= client_lng <= 180.0):
        return JSONResponse({"ok": False, "error": "Coordenadas inválidas."}, status_code=400)

    # heurística: se vierem trocadas (lat ~ negativo; lng ~ 36..43), inverte
    if (36.0 <= client_lng <= 43.5) and (-31.5 <= client_lat <= -5.0):
        client_lat, client_lng = client_lng, client_lat

    # calcula distância 1x
    km = haversine_km(client_lat, client_lng, COMPANY_LAT, COMPANY_LNG)

    # corta outliers "reais" do dia-a-dia
    MAX_DISTANCE_KM = float(os.getenv("MAX_DISTANCE_KM", "80"))
    if km > MAX_DISTANCE_KM:
        return JSONResponse(
            {"ok": False, "error": f"Localização incoerente ({km:.1f} km). Verifique morada/código postal."},
            status_code=400
        )

    # rede de segurança extrema
    if km > 1000:
        return JSONResponse(
            {"ok": False, "error": "Localização incoerente (distância > 1000 km). Verifique morada/CP/GPS."},
            status_code=400
        )

    # custos (agora sim)
    travel_cost = km * TRAVEL_RATE_EUR_PER_KM
    service_cost = calc_service_cost(categories, typology)
    total = service_cost + travel_cost

    breakdown = {
        "typology": typology,
        "hours": TYPOLOGY_HOURS.get(typology, 0),
        "per_category": {cat: CATEGORY_RATES.get(cat, 0.0) for cat in categories},
        "travel_rate": TRAVEL_RATE_EUR_PER_KM,
    }

    return {
        "ok": True,
        "distance_km": round(km, 2),
        "travel_cost": round(travel_cost, 2),
        "service_cost": round(service_cost, 2),
        "total": round(total, 2),
        "breakdown": breakdown
    }


@app.post("/api/geocode")
async def api_geocode(address: str = Form(...)):
    import os, re, requests, math

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) * R

    COMPANY_LAT = float(os.getenv("COMPANY_LAT", "0") or 0)
    COMPANY_LNG = float(os.getenv("COMPANY_LNG", "0") or 0)
    MAX_DIST_KM = float(os.getenv("MAX_DISTANCE_KM", "80"))  # salvaguarda
    

    # 1) Tentar OpenCage (se houver chave), com país PT e proximidade à sede
    OC_KEY = os.getenv("OPENCAGE_KEY")
    if OC_KEY:
        try:
            oc_params = {
                "q": address,
                "key": OC_KEY,
                "no_annotations": 1,
                "limit": 1,
                "language": "pt",
                "countrycode": "pt",
                "proximity": f"{COMPANY_LAT},{COMPANY_LNG}",
            }
            oc = requests.get(
                "https://api.opencagedata.com/geocode/v1/json",
                params=oc_params, timeout=8
            )
            if oc.status_code == 200:
                data = oc.json()
                if data.get("results"):
                    g = data["results"][0]["geometry"]
                    lat, lng = float(g["lat"]), float(g["lng"])
                    # Se ficar demasiado longe, tentamos CP
                    if COMPANY_LAT and COMPANY_LNG and haversine(COMPANY_LAT, COMPANY_LNG, lat, lng) > MAX_DIST_KM:
                        # Extrair CP e usar endpoint de CP
                        m = re.search(r"(\d{4}-\d{3})", address)
                        if m:
                            cp = m.group(1)
                            res = await api_postcode_geocode(postal_code=cp)
                            if isinstance(res, dict) and res.get("ok"):
                                return {"ok": True, "lat": res["lat"], "lng": res["lng"], "provider": "postcode_fallback"}

                    return {"ok": True, "lat": lat, "lng": lng, "provider": "opencage"}
        except Exception:
            # cai para o fallback abaixo
            pass

    # 2) Fallback: Nominatim PT
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "jsonv2", "limit": 1, "countrycodes": "pt"},
            headers={"User-Agent": "cleaning-quote-app/1.0 (support@example.com)"},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data:
            lat = float(data[0]["lat"]); lng = float(data[0]["lon"])
            # Se muito longe, tenta CP
            if COMPANY_LAT and COMPANY_LNG and haversine(COMPANY_LAT, COMPANY_LNG, lat, lng) > MAX_DIST_KM:
                m = re.search(r"(\d{4}-\d{3})", address)
                if m:
                    cp = m.group(1)
                    res = await api_postcode_geocode(postal_code=cp)  # chama a função async diretamente
                    if isinstance(res, dict) and res.get("ok"):
                        return {"ok": True, "lat": res["lat"], "lng": res["lng"], "provider": "postcode_fallback"}
                    
            return {"ok": True, "lat": lat, "lng": lng, "provider": "nominatim"}
        return JSONResponse({"ok": False, "error": "Morada não encontrada."}, status_code=400)
    except Exception:
        return JSONResponse({"ok": False, "error": "Erro de geocodificação."}, status_code=500)


PT_CP2_CENTROIDS = {
    "10": (38.72, -9.14), "11": (38.77, -9.18), "12": (38.77, -9.10),
    "13": (38.90, -9.16), "14": (39.10, -9.11), "15": (38.75, -9.39),
    "20": (39.23, -8.68), "21": (39.12, -8.53),
    "30": (40.20, -8.41), "31": (40.15, -8.49),
    "40": (41.15, -8.63), "41": (41.18, -8.60), "44": (41.35, -8.74),
    "47": (41.69, -8.83),
    "50": (40.66, -7.91), "51": (40.54, -7.27),
    "60": (39.82, -7.49), "61": (39.29, -7.42),
    "70": (38.57, -7.91), "78": (38.01, -7.86),
    "80": (37.02, -7.93), "81": (37.10, -8.24),
    "90": (32.66, -16.92), "95": (37.74, -25.67),
}

def extract_cp2(postal_code: str) -> str | None:
    m = re.search(r'(\d{4})', postal_code or '')
    if not m:
        return None
    return m.group(1)[:2]


@app.post("/api/postcode_geocode")
async def api_postcode_geocode(postal_code: str = Form(None)):
    import re, requests
    pc = (postal_code or "").strip()
    digits = re.sub(r"\D","", pc)
    if len(digits) == 7:
        pc_norm = f"{digits[:4]}-{digits[4:]}"
    else:
        pc_norm = pc
    if len(digits) < 4:
        return {"ok": False, "reason": "partial", "message": "Código postal incompleto."}
    if not re.match(r"^\d{4}(?:-\d{3})?$", pc_norm):
        return {"ok": False, "reason": "invalid", "message": "Código postal inválido."}
    try:
        resp = requests.get("https://nominatim.openstreetmap.org/search",
            params={"q": f"{pc_norm}, Portugal", "format":"jsonv2", "limit":1, "countrycodes":"pt"},
            headers={"User-Agent":"cleaning-quote-app/1.0"},
            timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                lat = float(data[0]["lat"]); lng=float(data[0]["lon"])
                return {"ok": True, "lat": lat, "lng": lng, "approx": False, "postal_code": pc_norm}
    except Exception:
        pass
    try:
        m = re.search(r"(\d{4})", pc_norm)
        if m:
            cp2 = m.group(1)[:2]
            if cp2 in PT_CP2_CENTROIDS:
                lat,lng = PT_CP2_CENTROIDS[cp2]
                return {"ok": True, "lat": lat, "lng": lng, "approx": True, "postal_code": pc_norm}
    except Exception:
        pass
    return {"ok": False, "reason": "unsupported", "message": "CP válido mas sem centroid mapeado."}

@app.post("/confirm")
async def confirm(
    request: Request,
    categories_csv: str = Form(...),
    typology: str = Form(...),
    address: str = Form(""),
    postal: str = Form(""),
    client_lat: str = Form(""),
    client_lng: str = Form(""),
    total: str = Form(...),
    products_option: str = Form("cliente"),
):
    categories = [c.strip() for c in categories_csv.split(",") if c.strip()]
    ctx = {
        "request": request,
        "categories": categories,
        "typology": typology,
        "address": address,
        "postal": postal,
        "client_lat": client_lat,
        "client_lng": client_lng,
        "total": total,
        "products_option": products_option,  
    }
    return templates.TemplateResponse("confirm.html", ctx)


def send_email_notification(payload: dict):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and NOTIFY_TO):
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"Novo pedido de limpeza — {payload.get('nome') or 'Cliente'}"
        msg["From"] = SENDER_FROM
        msg["To"] = NOTIFY_TO
        body = "\n".join([f"{k}: {v}" for k, v in payload.items()])
        msg.set_content(body)

        if SMTP_PORT == 465 or SMTP_SECURE == 'ssl':
            import smtplib
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        return True
    except Exception:
        return False


@app.post("/submit_lead")
async def submit_lead(
    request: Request,
    nome: str = Form(""),
    email: str = Form(""),
    telefone: str = Form(""),
    frequencia: str = Form("Único"),
    data_pref: str = Form(""),
    janela_horaria: str = Form(""),
    observacoes: str = Form(""),
    categories_csv: str = Form(...),
    typology: str = Form(...),
    address: str = Form(""),
    postal: str = Form(""),
    client_lat: str = Form(""),
    client_lng: str = Form(""),
    total: str = Form(...),
    consent: str = Form(None),
    products_option: str = Form("cliente"),
):
    if not (email or telefone):
        return templates.TemplateResponse("confirm.html", {
            "request": request, "error": "Indique email ou telefone.",
            "categories": [c.strip() for c in categories_csv.split(",") if c.strip()],
            "typology": typology, "address": address, "postal": postal,
            "client_lat": client_lat, "client_lng": client_lng, "total": total,
            "products_option": products_option,
            "form": {"nome": nome, "email": email, "telefone": telefone, "frequencia": frequencia,
                     "data_pref": data_pref, "janela_horaria": janela_horaria, "observacoes": observacoes}
        })

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "nome": nome, "email": email, "telefone": telefone,
        "frequencia": frequencia, "data_pref": data_pref, "janela_horaria": janela_horaria,
        "observacoes": observacoes, "categories": categories_csv, "typology": typology,
        "address": address, "postal": postal, "client_lat": client_lat, "client_lng": client_lng,
         "products_option": products_option,
        "total": total,
    }

    is_new_file = not LEADS_CSV.exists()
    with LEADS_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(payload.keys()))
        if is_new_file:
            w.writeheader()
        w.writerow(payload)

    email_ok = send_email_notification(payload)

    return templates.TemplateResponse("thankyou.html", {
        "request": request,
        "nome": nome or "Cliente",
        "email_ok": email_ok,
        "total": total
    })



@app.get("/condominio")
async def condominio_form(request: Request):
    return templates.TemplateResponse("condominio.html", {"request": request})

@app.post("/condominio_submit")
async def condominio_submit(
    request: Request,
    nome: str = Form(""),
    email: str = Form(""),
    telefone: str = Form(""),
    morada: str = Form(""),
    fraccoes: str = Form(""),
    mensagem: str = Form(""),
):
    # Guardar CSV específico para condomínios
    from datetime import datetime
    from pathlib import Path
    LEADS_DIR = Path("./data")
    LEADS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = LEADS_DIR / "condominio_leads.csv"
    is_new_file = not csv_path.exists()
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "nome": nome,
        "email": email,
        "telefone": telefone,
        "morada": morada,
        "fraccoes": fraccoes,
        "mensagem": mensagem,
        "origem": "condominio",
    }

    try:
        import csv
        with csv_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(payload.keys()))
            if is_new_file:
                w.writeheader()
            w.writerow(payload)
    except Exception:
        pass

    # Envio de email interno (opcional, consoante configuração existente)
    email_ok = None
    try:
        email_ok = send_email_notification(payload)
    except Exception:
        email_ok = None

    return templates.TemplateResponse("condominio_thanks.html", {
        "request": request,
        "nome": nome or "Cliente",
        "email_ok": email_ok
    })


@app.get("/admin/check_emails")
async def admin_check_emails():
    """
    Dispara a leitura de emails não lidos da INBOX (Gmail IMAP) e regista-os em data/leads.csv.
    Requer variáveis EMAIL_USER e EMAIL_PASS (app password) no .env.
    """
    try:
        processed = email_receiver.fetch_unread_to_leads()
        return {"ok": True, "processed": processed, "count": len(processed)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# --- debug: simple version endpoint (safe to remove) ---


@app.get("/api/debug_env")
def api_debug_env():
    return {
        "COMPANY_LAT": COMPANY_LAT,
        "COMPANY_LNG": COMPANY_LNG,
        "PRICE_PER_KM": TRAVEL_RATE_EUR_PER_KM
    }

@app.get("/version")
def _version():
    return "v7"
# --- end debug ---
