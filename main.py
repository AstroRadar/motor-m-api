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
    # Поддерживаем все варианты: points, points_route, points_order
    points = data.get("points") or data.get("points_route") or data.get("points_order", [])
    
    # Если points_order с полными данными, извлекаем только coords
    if points and isinstance(points[0], dict) and "coords" in points[0]:
        points = [{"lat": p["coords"]["lat"], "lng": p["coords"]["lng"]} for p in points]
    
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

    # Нормализуем points для создания маршрута
    points_for_route = None
    if "points_order" in data:
        # Извлекаем только координаты из points_order для /route
        points_for_route = [{"lat": p["coords"]["lat"], "lng": p["coords"]["lng"]} for p in data["points_order"]]
    elif "points_route" in data:
        points_for_route = data["points_route"]
    elif "points" in data:
        points_data = data["points"]
        # Проверяем формат: если это полные данные (с coords), извлекаем координаты
        if isinstance(points_data[0], dict) and "coords" in points_data[0]:
            points_for_route = [{"lat": p["coords"]["lat"], "lng": p["coords"]["lng"]} for p in points_data]
        else:
            points_for_route = points_data

    # Шаг 1: Получаем id_route если его нет
    if "id_route" not in data or not data["id_route"]:
        if not points_for_route:
            raise HTTPException(status_code=400, detail="Missing points for route")
        
        route_payload = {"id_taxi": ID_TAXI, "points": points_for_route}
        print(f"🗺️ Creating route with {len(points_for_route)} points")
        r = requests.post(f"{TMOTOR_API}/route", json=route_payload, timeout=20)
        route_result = r.json()
        
        if not route_result.get("status"):
            print(f"❌ Route creation failed: {route_result.get('error')}")
            return route_result
        
        data["id_route"] = route_result.get("id", 0)
        print(f"📍 Got id_route: {data['id_route']}")

    # Определяем какой формат points использовать для Bee API
    # Bee ожидает points_order (полные данные) в /order
    if "points_order" in data:
        # Уже в правильном формате, оставляем как есть
        print("✅ Using points_order (full data)")
    elif "points" in data:
        # Если points с полными данными (coords + city + street + home)
        points_data = data["points"]
        if isinstance(points_data[0], dict) and "coords" in points_data[0]:
            data["points_order"] = points_data
            del data["points"]
            print("🔄 Converted points → points_order")
        else:
            # Простые координаты - оставляем как points
            print("⚠️ Using simple points format")
    
    # Чистим payload от полей, которые могут вызывать bee_500
    if "advanced" in data and data["advanced"] is None:
        del data["advanced"]
        print("🧹 Removed advanced: null")
    
    if "comment" in data and not str(data["comment"]).strip():
        del data["comment"]
        print("🧹 Removed empty comment")
    
    # Убираем служебные поля
    data.pop("do_calculate", None)
    data.pop("points_route", None)
    data.pop("points", None)  # Убираем points если есть points_order

    # Шаг 2: Создаем заказ
    print(f"📤 Sending to Bee, keys: {list(data.keys())}")
    print(f"📦 Payload preview: id_taxi={data.get('id_taxi')}, id_route={data.get('id_route')}, phone={data.get('phone')}, points_order={len(data.get('points_order', []))} points")
    
    r = requests.post(f"{TMOTOR_API}/order", json=data, timeout=20)
    bee_response = r.json()
    
    print(f"📨 Bee response status: {bee_response.get('status')}")
    if not bee_response.get('status'):
        print(f"❌ Bee error: {bee_response.get('error')}")
    else:
        order_id = bee_response.get('response', {}).get('order', {}).get('id_order', 'unknown')
        print(f"✅ Order created: {order_id}")
    
    return bee_response
