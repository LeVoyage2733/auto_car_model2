#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from ride_service_interfaces.msg import RideRequest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import threading
import json
import os

# --- [ROS 2 노드] ---
class RidePublisher(Node):
    def __init__(self):
        super().__init__('ride_server_node')
        self.publisher_ = self.create_publisher(RideRequest, '/ride_request', 10)
        
        # 정류장 좌표 (1~6번)
        self.stations = {
            1: {'x': 5.12, 'y': 16.0}, 2: {'x': 36.2, 'y': 27.7},
            3: {'x': 78.3, 'y': 14.2}, 4: {'x': 59.6, 'y': 61.9},
            5: {'x': 45.1, 'y': 57.9}, 6: {'x': 5.5, 'y': 54.1}
        }

    def publish_ride(self, start_idx, end_idx, user_id="web_user"):
        if start_idx not in self.stations or end_idx not in self.stations:
            return False
            
        msg = RideRequest()
        msg.pickup_location.x = self.stations[start_idx]['x']
        msg.pickup_location.y = self.stations[start_idx]['y']
        msg.dropoff_location.x = self.stations[end_idx]['x']
        msg.dropoff_location.y = self.stations[end_idx]['y']
        
        self.publisher_.publish(msg)
        self.get_logger().info(f"📡 [WebSocket] 호출 수신: {user_id} ({start_idx} -> {end_idx})")
        return True

# --- [FastAPI 설정] ---
app = FastAPI()
ros_node = None

# 1. 기본 웹페이지 (테스트용)
@app.get("/")
async def get():
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>자율주행 택시 호출</title>
        </head>
        <body>
            <h1>🚖 WebSocket 택시 호출</h1>
            <button onclick="callTaxi(1, 3)">1번 -> 3번 호출</button>
            <button onclick="callTaxi(3, 2)">3번 -> 2번 호출</button>
            <hr>
            <div id="status">상태: 대기 중</div>

            <script>
                var ws = new WebSocket("ws://" + window.location.host + "/ws/call");

                ws.onmessage = function(event) {
                    var messages = document.getElementById('status');
                    messages.innerHTML = "상태: " + event.data;
                };

                function callTaxi(start, end) {
                    if(ws.readyState === WebSocket.OPEN) {
                        var data = JSON.stringify({start: start, end: end, user: "guest"});
                        ws.send(data);
                        document.getElementById('status').innerHTML = "상태: 호출 전송 중...";
                    } else {
                        alert("서버와 연결되지 않았습니다.");
                    }
                }
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html_content)

# 2. WebSocket 엔드포인트 (친구 코드가 접속할 곳)
@app.websocket("/ws/call")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("✅ [SYSTEM] 웹 클라이언트 연결됨")
    try:
        while True:
            # 데이터 수신 (JSON 형태: {"start": 1, "end": 3})
            data = await websocket.receive_text()
            try:
                req = json.loads(data)
                start = int(req.get("start", 1))
                end = int(req.get("end", 3))
                user = req.get("user", "unknown")
                
                # ROS 2 토픽 발행
                if ros_node:
                    ros_node.publish_ride(start, end, user)
                    await websocket.send_text(f"배차 성공: {start}->{end}")
                else:
                    await websocket.send_text("오류: ROS 노드 없음")
                    
            except Exception as e:
                print(f"⚠️ 데이터 처리 오류: {e}")
                await websocket.send_text("오류: 데이터 형식 불일치")

    except WebSocketDisconnect:
        print("⚠️ [SYSTEM] 연결 끊김")

# 3. 메인 실행
def main():
    global ros_node
    rclpy.init()
    ros_node = RidePublisher()
    
    spin_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    spin_thread.start()
    
    print("🚀 [WebSocket 서버 시작] ws://0.0.0.0:8000/ws/call")
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
    ros_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
