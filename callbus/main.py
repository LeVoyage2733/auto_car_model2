from fastapi import FastAPI, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pathlib import Path
import os, yaml
import threading
import json

# --- [ROS 2 관련 임포트] ---
import rclpy
from rclpy.node import Node
from ride_service_interfaces.msg import RideRequest

# --- [ROS 2 노드 클래스 정의] ---
class RidePublisher(Node):
    def __init__(self):
        super().__init__('web_ride_bridge')
        self.publisher_ = self.create_publisher(RideRequest, '/ride_request', 10)
        
        self.stations = {
            1: {'x': 5.12, 'y': 16.0}, 2: {'x': 36.2, 'y': 27.7},
            3: {'x': 78.3, 'y': 14.2}, 4: {'x': 59.6, 'y': 61.9},
            5: {'x': 45.1, 'y': 57.9}, 6: {'x': 5.5, 'y': 54.1}
        }

    def dispatch_taxi(self, start_idx, end_idx, user_id="web_user"):
        if start_idx not in self.stations or end_idx not in self.stations:
            self.get_logger().error(f"❌ 잘못된 정류장: {start_idx}->{end_idx}")
            return False
        
        msg = RideRequest()
        msg.pickup_location.x = self.stations[start_idx]['x']
        msg.pickup_location.y = self.stations[start_idx]['y']
        msg.dropoff_location.x = self.stations[end_idx]['x']
        msg.dropoff_location.y = self.stations[end_idx]['y']
        
        self.publisher_.publish(msg)
        self.get_logger().info(f"📢 [WEB] 차량 호출 전송: {user_id} ({start_idx} -> {end_idx})")
        return True

# --- [FastAPI 및 ROS 초기화] ---
app = FastAPI()
BASE_DIR = Path(__file__).parent

# ROS 2 스레드 실행
rclpy.init()
ros_node = RidePublisher()
spin_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
spin_thread.start()

# --- [WebSocket 관리자] ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- [라우터] ---
@app.get("/")
def index():
    path = Path(__file__).parent / "statics" / "index.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

@app.get("/호출예약")
def reservation():
    path = Path(__file__).parent / "statics" / "reservation_1.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

@app.post("/호출예약")
async def post_reservation(
    name: str = Form(...), phone: str = Form(...), user_id: str = Form(...),
    emergency: str = Form(""), passengers: int = Form(...), assist: bool = Form(False)
):
    new_data = {user_id: {"name": name, "phone": phone, "emergency": emergency, "passengers": passengers, "assist": assist}}
    file_path = BASE_DIR / "userinfo.yml"
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f: existing = yaml.safe_load(f) or {}
    else: existing = {}
    existing.update(new_data)
    with file_path.open("w", encoding="utf-8") as f: yaml.dump(existing, f, allow_unicode=True, sort_keys=False)
    return HTMLResponse(f"<script>location.href='/호출위치선택?user_id={user_id}';</script>")

@app.get("/호출위치선택")
def location():
    path = Path(__file__).parent / "statics" / "reservation_2.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

@app.post("/호출위치선택")
async def post_LocationTime(
    user_id: str = Form(...), date: str = Form(...), arrival_time: str = Form(...),
    start_node: int = Form(...), end_node: int = Form(...)
):
    # 1. 파일 저장
    new_data = {user_id: {"date": date, "time": arrival_time, "start": start_node, "end": end_node}}
    file_path = BASE_DIR / "reservation.yml"
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f: existing = yaml.safe_load(f) or {}
    else: existing = {}
    existing.update(new_data)
    with file_path.open("w", encoding="utf-8") as f: yaml.dump(existing, f, allow_unicode=True, sort_keys=False)

    # 2. 파일 다시 읽어서 ROS 호출 (데이터 무결성 확인)
    if ros_node:
        with file_path.open("r", encoding="utf-8") as f: saved_db = yaml.safe_load(f) or {}
        user_record = saved_db.get(user_id, {})
        s = int(user_record.get("start"))
        e = int(user_record.get("end"))
        
        ros_node.dispatch_taxi(s, e, user_id)
        
    # 3. WebSocket 브로드캐스트
    await manager.broadcast(f"CALL:{user_id},{start_node},{end_node}")

    return HTMLResponse("""<script>alert("✅ 예약 완료! 택시가 출발합니다."); window.location.href = "/경로및소요시간";</script>""")

@app.get("/경로및소요시간")
def time():
    path = Path(__file__).parent / "statics" / "reservation_3.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

# --- [WebSocket] ---
@app.websocket("/ws/call")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            req = json.loads(data)
            start = int(req.get("start", 1))
            end = int(req.get("end", 3))
            user = req.get("user", "unknown")
            
            if ros_node:
                ros_node.dispatch_taxi(start, end, user)
                await websocket.send_text(f"배차 성공: {start}->{end}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)
