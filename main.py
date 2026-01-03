import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

TMOTOR_API = "https://tmotorm.dyndns.org/taxi/api/v2/web"

RECAPTCHA_SECRET = os.getenv("RECAPTCHA_SECRET")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN")
ID_TAXI = int(os.getenv("ID_TAXI", "340"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN else ["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

def verify_recaptcha(token: str):
    if not RECAPTCHA_SECRET:
        raise HTTPException(status_code=500, detail="RECAPTCHA_SECRET is not set")

    r = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={"secret": RECAPTCHA_SECRET, "response": token},
        timeout=10,
    )
    result = r.json()
    if not result.get("success"):
        raise HTTPException(status_code=403, detail={"recaptcha": "failed", "google": result})

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/route")
async def build_route(data: dict):
    payload = {"id_taxi": ID_TAXI, "points": data["points"]}
    r = requests.post(f"{TMOTOR_API}/route", json=payload, timeout=20)
    return r.json()

@app.post("/calculate")
async def calculate(data: dict):
    payload = {"id_taxi": ID_TAXI, "id": data["id"], "points": data["points"]}
    r = requests.post(f"{TMOTOR_API}/order/calculate", json=payload, timeout=20)
    return r.json()

@app.post("/order")
async def create_order(request: Request):
    data = await request.json()

    verify_recaptcha(data["recaptcha"])

    payload = {
        "id_taxi": ID_TAXI,
        "id_route": data["id_route"],
        "phone": data["phone"],
        "comment": data.get("comment", ""),
        "tariff": data["tariff"],
        "pay_type": data.get("pay_type", 0),
        "advanced": None,
    }

    r = requests.post(f"{TMOTOR_API}/order", json=payload, timeout=20)
    return r.json()
