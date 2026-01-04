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
        print("⚠️ RECAPTCHA_SECRET not set, skipping verification")
        return True
    
    r = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={"secret": RECAPTCHA_SECRET, "response": token},
        timeout=10,
    )
    result = r.json()
    print(f"🔐 Google reCAPTCHA verify result: {result}")
    
    if not result.get("success"):
        print(f"❌ Google reCAPTCHA validation failed: {result}")
        raise HTTPException(status_code=403, detail={"recaptcha": "failed", "google": result})
    
    print("✅ Google reCAPTCHA validation passed")
    return True

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
    
    print(f"📥 Received order request, keys: {list(data.keys())}")

    # Проверка reCAPTCHA: токен приходит в g-recaptcha-response
    recaptcha_token = data.get("g-recaptcha-response") or data.get("recaptcha")
    
    if recaptcha_token and RECAPTCHA_SECRET:
        print(f"🔐 Verifying reCAPTCHA token (length: {len(recaptcha_token)})")
        verify_recaptcha(recaptcha_token)
    else:
        print(f"⏭️ Skipping reCAPTCHA verification (token: {bool(recaptcha_token)}, secret: {bool(RECAPTCHA_SECRET)})")

    # Добавляем id_taxi если его нет
    if "id_taxi" not in data:
        data["id_taxi"] = ID_TAXI

    # Шаг 1: Получаем id_route если его нет
    if "id_route" not in data or not data["id_route"]:
        points = data.get("points", [])
        
        if not points:
            raise HTTPException(status_code=400, detail="Missing points for route")
        
        route_payload = {"id_taxi": ID_TAXI, "points": points}
        r = requests.post(f"{TMOTOR_API}/route", json=route_payload, timeout=20)
        route_result = r.json()
        
        if not route_result.get("status"):
            return route_result
        
        data["id_route"] = route_result.get("id", 0)
        print(f"📍 Got id_route from /route: {data['id_route']}")

    # Шаг 2: Создаем заказ
    print(f"📤 Sending order to Bee API with keys: {list(data.keys())}")
    r = requests.post(f"{TMOTOR_API}/order", json=data, timeout=20)
    bee_response = r.json()
    print(f"📨 Bee API response: {bee_response}")
    return bee_response
