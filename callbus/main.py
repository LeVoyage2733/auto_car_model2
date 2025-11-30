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
        
        # 정류장 좌표 데이터베이스 (1~6번)
        self.stations = {
            1: {'x': 5.12, 'y': 16.0},   # 태초마을
            2: {'x': 36.2, 'y': 27.7},   # 시장
            3: {'x': 78.3, 'y': 14.2},   # x마을
            4: {'x': 59.6, 'y': 61.9},   # 먼 마을
            5: {'x': 45.1, 'y': 57.9},   # 갈림길
            6: {'x': 5.5, 'y': 54.1}     # 크 마을
        }

    def dispatch_taxi(self, start_idx, end_idx, user_id="web_user"):
        # 유효하지 않은 정류장 번호면 무시
        if start_idx not in self.stations or end_idx not in self.stations:
            self.get_logger().error(f"❌ 잘못된 정류장 번호: {start_idx} -> {end_idx}")
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

# ROS 2 스레드 실행 (서버와 함께 돌아가도록)
rclpy.init()
ros_node = RidePublisher()
spin_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
spin_thread.start()

# =========================================================
# 웹 페이지 라우터 (HTML 서빙 및 로직 처리)
# =========================================================

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
    name: str = Form(...), phone: int = Form(...), user_id: str = Form(...),
    emergency: int = Form(...), passengers: int = Form(...), assist: bool = Form(False)
):
    # 1. 사용자 정보 저장
    new_data = {user_id: {"name": name, "phone": phone, "emergency": emergency, "passengers": passengers, "assist": assist}}
    file_path = BASE_DIR / "userinfo.yml"
    
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f: existing = yaml.safe_load(f) or {}
    else: existing = {}

    existing.update(new_data)
    with file_path.open("w", encoding="utf-8") as f:
        yaml.dump(existing, f, allow_unicode=True, sort_keys=False)

    # 2. 다음 페이지로 이동
    return HTMLResponse(f"""
        <script>
            alert("정보 등록 완료! 위치 선택으로 이동합니다.");
            location.href='/호출위치선택?user_id={user_id}';
        </script>
    """)

@app.get("/호출위치선택")
def location():
    path = Path(__file__).parent / "statics" / "reservation_2.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

# --- [핵심] 호출 확정 및 ROS 명령 전송 ---
@app.post("/호출위치선택")
async def post_LocationTime(
    user_id: str = Form(...),
    date: str = Form(...),
    arrival_time: str = Form(...),
    start_node: int = Form(...),  # 출발지 번호 (HTML에서 전송됨)
    end_node: int = Form(...)     # 도착지 번호 (HTML에서 전송됨)
):
    try:
        # 1. [검증] 유효한 사용자인지 확인
        user_file = BASE_DIR / "userinfo.yml"
        if user_file.exists():
            with user_file.open("r", encoding="utf-8") as f:
                users = yaml.safe_load(f) or {}
        else:
            users = {}

        if user_id not in users:
             return HTMLResponse("""
                <script>
                    alert("❌ 등록되지 않은 사용자입니다. 처음부터 다시 시도해주세요.");
                    window.location.href = "/호출예약";
                </script>
            """)

        # 2. [저장] 예약 정보 저장 (reservation.yml)
        new_data = {
            user_id: {
                "date": date,
                "time": arrival_time,
                "start": start_node,
                "end": end_node
            }
        }
        
        res_file = BASE_DIR / "reservation.yml"
        if res_file.exists():
            with res_file.open("r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        else:
            existing = {}

        existing.update(new_data)
        
        with res_file.open("w", encoding="utf-8") as f:
            yaml.dump(existing, f, allow_unicode=True, sort_keys=False)

        # 3. [호출] 자율주행차에게 출발 명령 전송 🚀
        if ros_node:
            # 사용자가 선택한 출발지->도착지로 이동 명령
            success = ros_node.dispatch_taxi(start_node, end_node, user_id)
            if not success:
                 raise Exception("잘못된 정류장 번호입니다.")
        else:
            print("⚠️ ROS 노드가 실행되지 않았습니다.")

        # 4. [성공] 알림창 띄우고 다음 페이지로
        return HTMLResponse("""
            <script>
                alert("✅ 예약 및 호출이 완료되었습니다! 차량이 출발합니다.");
                window.location.href = "/경로및소요시간";
            </script>
        """)

    except Exception as e:
        # 5. [실패] 에러 팝업
        print(f"❌ 서버 에러 발생: {e}")
        return HTMLResponse(f"""
            <script>
                alert("시스템 오류가 발생했습니다: {e}");
                window.history.back();
            </script>
        """)

@app.get("/경로및소요시간")
def time():
    path = Path(__file__).parent / "statics" / "reservation_3.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

# --- [WebSocket 엔드포인트 (실시간 제어용)] ---
@app.websocket("/ws/call")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
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
        pass

if __name__ == '__main__':
    # 직접 실행 시 uvicorn 가동
    uvicorn.run(app, host="0.0.0.0", port=8000)
