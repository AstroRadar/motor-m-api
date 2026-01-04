import os
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

TMOTOR_API = "https://tmotorm.dyndns.org/taxi/api/v2/web"

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN")
ID_TAXI = int(os.getenv("ID_TAXI", "340"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN] if ALLOWED_ORIGIN else ["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/route")
async def build_route(data: dict):
    # Поддерживаем оба формата: points и points_route
    points = data.get("points") or data.get("points_route", [])
    payload = {"id_taxi": ID_TAXI, "points": points}
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
    
    print(f"📥 Received order, keys: {list(data.keys())}")

    # Добавляем id_taxi если его нет
    if "id_taxi" not in data:
        data["id_taxi"] = ID_TAXI

    # Нормализуем points: поддерживаем points, points_order, points_route
    if "points" not in data:
        if "points_order" in data:
            data["points"] = data.pop("points_order")
            print("🔄 Converted points_order → points")
        elif "points_route" in data:
            data["points"] = data.pop("points_route")
            print("🔄 Converted points_route → points")

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
        print(f"📍 Got id_route: {data['id_route']}")

    # Чистим payload от полей, которые могут вызывать bee_500
    if "advanced" in data and data["advanced"] is None:
        del data["advanced"]
        print("🧹 Removed advanced: null")
    
    if "comment" in data and not str(data["comment"]).strip():
        del data["comment"]
        print("🧹 Removed empty comment")
    
    # Убираем служебные поля order_form.js
    data.pop("do_calculate", None)
    data.pop("points_route", None)

    # Шаг 2: Создаем заказ
    print(f"📤 Sending to Bee, keys: {list(data.keys())}")
    r = requests.post(f"{TMOTOR_API}/order", json=data, timeout=20)
    bee_response = r.json()
    print(f"📨 Bee response status: {bee_response.get('status')}, error: {bee_response.get('error')}")
    return bee_response
