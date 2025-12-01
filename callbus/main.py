from fastapi import FastAPI, HTTPException, Form, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import yaml
from typing import List



app = FastAPI()

# --- 연결 관리자 (ROS 차량 관리) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        # 연결된 모든 차량에게 메시지 전송
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()
# ----------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

# --- 1. 기본 페이지 ---
@app.get("/")
def index():
    path = BASE_DIR / "statics" / "index.html"
    if not path.exists(): return HTMLResponse("index.html 없음", 404)
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

# --- 2. 호출 예약 (사용자 정보 입력) ---
@app.get("/호출예약")
def reservation():
    path = BASE_DIR / "statics" / "reservation_1.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

@app.post("/호출예약")
async def post_reservation(
    name: str = Form(...),
    phone: str = Form(...),
    user_id: str = Form(...),
    emergency: str  = Form(""),
    passengers: int = Form(...),
    assist: bool = Form(False)
):
    # print(name, phone, user_id, emergency) # 테스트용


    new_data = {
        user_id: {
            "name": name,
            "phone": phone,
            "emergency": emergency,
            "passengers": passengers, 
            "assist": assist
        }
    }

    file_path = BASE_DIR / "userinfo.yml"

    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    else:
        existing = {}

    if user_id not in existing:
        return HTMLResponse("""
            <script>
              alert("등록되지 않은 ID입니다");  
              location.href="/호출예약";
            </script>
        """)

    # 안전하게 현재 등록된 값 꺼내기
    name_value = existing.get(user_id, {}).get("name")
    phone_value = existing.get(user_id, {}).get("phone")
    # pass_value = existing.get(user_id, {}).get("passengers")
    # assist_value = existing.get(user_id, {}).get("assist")

    # print(name_value, phone_value, pass_value, assist_value) # 테스트 용

    if (user_id in existing) & (name_value == 'empty' and phone_value == 'empty'):
        existing.update(new_data)
        with file_path.open("w", encoding="utf-8") as f:
            yaml.dump(existing, f, allow_unicode=True, sort_keys=False)
        return HTMLResponse(f"""
            <script>
              alert("정보 업데이트 성공!");
              location.href="/호출예약";   
              window.location.href = '/호출위치선택?user_id={user_id}';  
            </script>
        """)

    elif (user_id in existing) & (name_value == name and phone_value == phone):
        existing.update(new_data)
        with file_path.open("w", encoding="utf-8") as f:
            yaml.dump(existing, f, allow_unicode=True, sort_keys=False)
        return HTMLResponse(f"""
            <script>
              alert("본인인증 완료!");
              location.href="/호출예약"; 
              window.location.href = "/호출위치선택?user_id={user_id}";
            </script>
        """)

    return HTMLResponse("""
        <script>
          alert("예약자 정보가 일치하지 않습니다");
          location.href="/호출예약";
        </script>
    """)

# --- 3. 호출 위치 선택 (여기서는 저장만) ---
@app.get("/호출위치선택")
def location():
    path = BASE_DIR / "statics" / "reservation_2.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

@app.post("/호출위치선택")
async def post_LocationTime(
    user_id: str = Form(...), 
    start: str = Form(...),   # 출발지
    end: str = Form(...),     # 목적지
    date: str = Form(...), 
    arrival_time: str = Form(...)
):
    print(f"--> [페이지2] 예약 정보 저장: {user_id} | {start} -> {end}")

    # 1. 파일 저장
    new_data = {
        user_id: {
            "start": start,
            "end": end,
            "date": date, 
            "time": arrival_time
        }
    }
    file_path = BASE_DIR / "reservation.yml"
    
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f: existing = yaml.safe_load(f) or {}
    else: existing = {}
    
    existing.update(new_data)
    with file_path.open("w", encoding="utf-8") as f: yaml.dump(existing, f, allow_unicode=True, sort_keys=False)

    # ROS 전송 없이, user_id를 달고 페이지 3으로 이동
    return HTMLResponse(f"""
        <script>
          alert("저장되었습니다!");
          window.location.href = "/경로및소요시간?user_id={user_id}";
        </script>
    """)


# --- 4. 경로 및 소요시간 (완료 버튼 누르면 전송) ---
@app.get("/경로및소요시간")
def time():
    path = BASE_DIR / "statics" / "reservation_3.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"), status_code=200)

# 완료 버튼 처리
@app.post("/예약완료")
async def complete_reservation(user_id: str = Form(...)):
    print(f"전송 요청 ID: {user_id}")
    
    # 1. 파일에서 저장된 정보(start, end) 꺼내기
    file_path = BASE_DIR / "reservation.yml"
    if not file_path.exists():
        return JSONResponse({"status": "error", "message": "예약 정보 파일이 없습니다."})

    with file_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    user_data = data.get(user_id)
    if not user_data:
        return JSONResponse({"status": "error", "message": "해당 ID의 예약 정보가 없습니다."})

    start_val = user_data.get("start")
    end_val = user_data.get("end")

    # 2. ROS(차량)에게 데이터 쏘기
    msg_to_ros = f"CALL:{user_id},{start_val},{end_val}"
    await manager.broadcast(msg_to_ros)
    
    print(f"--> [서버 -> ROS] 전송 완료: {msg_to_ros}")

    return JSONResponse({"status": "success", "message": "차량 호출이 완료되었습니다!"})


# --- 5. 예약 확인 ---
@app.get("/예약확인")
def check():
    path = Path(__file__).parent / "statics" / "check_number.html" 
    html_content = path.read_text(encoding = "utf-8")
    return HTMLResponse(content = html_content, status_code = 200)
@app.post("/예약확인")
async def post_reservation(
    checkcode: str = Form(...)
):
    file_path = BASE_DIR / "reservation.yml"
    

    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    else:
        existing = {}

    start_value = existing.get(checkcode, {}).get("start")

    if (checkcode in existing) and start_value != 'empty':
        return HTMLResponse(f"""
            <script>
            alert("식별번호가 확인되었습니다!");
            window.location.href = "/예약정보확인?code={checkcode}";
            </script>
        """)
    return HTMLResponse("""
            <script>
            alert("옳바르지 않은 식별번호입니다. \\n식별번호를 다시 확인해주세요.");
            window.location.href= "/예약확인";
            </script>
        """)

@app.get("/예약정보확인")
def check():
    path = Path(__file__).parent / "statics" / "check_reservation.html" 
    html_content = path.read_text(encoding = "utf-8")
    return HTMLResponse(content = html_content, status_code = 200)
@app.post("/api/reservation/cancel")
def cancel_reservation(code: str = Query(...)):
    """
    /api/reservation/cancel?code=식별번호
    로 들어온 예약을 'empty' 값으로 초기화
    - userinfo.yml
    - reservation.yml
    """
    # reservation.yml 초기화
    reservation_path = BASE_DIR / "reservation.yml"
    if reservation_path.exists():
        with reservation_path.open("r", encoding="utf-8") as f:
            reservation = yaml.safe_load(f) or {}
    else:
        reservation = {}

    reservation[code] = {
        "start": "empty",
        "end": "empty",
        "date": "empty",
        "time": "empty",
    }

    with reservation_path.open("w", encoding="utf-8") as f:
        yaml.dump(reservation, f, allow_unicode=True, sort_keys=False)

    return JSONResponse(
        {"status": "success", "message": "예약이 정상적으로 취소되었습니다."}
    )


# 예약정보 조회
@app.get("/api/reservation")
def get_reservation(code: str = Query(...)):
    """
    식별번호(code = user_id)로 예약 상세 정보 조회
    - 사용자 기본 정보: userinfo.yml
    - 위치/시간 정보: reservation.yml
    를 합쳐서 JSON으로 반환
    """

    userinfo_path = BASE_DIR / "userinfo.yml"
    reservation_path = BASE_DIR / "reservation.yml"

    # 파일 존재 여부 체크
    if not userinfo_path.exists() or not reservation_path.exists():
        raise HTTPException(status_code=404, detail="예약 정보를 찾을 수 없습니다.")

    with userinfo_path.open("r", encoding="utf-8") as f:
        userinfo = yaml.safe_load(f) or {}

    with reservation_path.open("r", encoding="utf-8") as f:
        reservations = yaml.safe_load(f) or {}

    basic = userinfo.get(code)
    detail = reservations.get(code)

    if not basic or not detail:
        raise HTTPException(status_code=404, detail="해당 식별번호의 예약 정보가 없습니다.")

    # 프론트에서 쓸 수 있게 합쳐서 반환
    result = {
        "name": basic.get("name"),
        "phone": basic.get("phone"),
        "emergency": basic.get("emergency"),
        "passengers": basic.get("passengers"),
        "assist": basic.get("assist"),
        "start": detail.get("start"),
        "end": detail.get("end"),
        "date": detail.get("date"),
        "time": detail.get("time"),
    }

    return JSONResponse(content=result)

# --- WebSocket (ROS 연결용) ---
@app.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_socket(websocket: WebSocket, vehicle_id: str):
    await manager.connect(websocket)
    print(f"✅ [SYSTEM] 차량 연결됨: {vehicle_id}")
    try:
        while True:
            data = await websocket.receive_text()
            print(f"📩 [차량 -> 서버] {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"⚠️ [SYSTEM] 차량 연결 끊김: {vehicle_id}")
