#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from ride_service_interfaces.msg import RideRequest
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import threading

# 1. 데이터 모델 정의 (앱에서 이렇게 보내줘야 함)
class CallData(BaseModel):
    user_id: str
    start_node: int  # 출발 정류장 번호 (1~6)
    end_node: int    # 도착 정류장 번호 (1~6)

# 2. ROS 2 퍼블리셔 노드 (메시지 발송용)
class RidePublisher(Node):
    def __init__(self):
        super().__init__('ride_server_node')
        self.publisher_ = self.create_publisher(RideRequest, '/ride_request', 10)
        
        # 정류장 좌표 데이터베이스 (매니저와 동일하게 맞춤)
        self.stations = {
            1: {'x': 5.12, 'y': 16.0},   # 태초마을
            2: {'x': 36.2, 'y': 27.7},   # 시장
            3: {'x': 78.3, 'y': 14.2},   # x마을
            4: {'x': 59.6, 'y': 61.9},   # 먼 마을
            5: {'x': 45.1, 'y': 57.9},   # 갈림길
            6: {'x': 5.5, 'y': 54.1}     # 크 마을
        }

    def publish_ride(self, data: CallData):
        if data.start_node not in self.stations or data.end_node not in self.stations:
            return False
            
        msg = RideRequest()
        # 출발지 좌표
        msg.pickup_location.x = self.stations[data.start_node]['x']
        msg.pickup_location.y = self.stations[data.start_node]['y']
        # 목적지 좌표
        msg.dropoff_location.x = self.stations[data.end_node]['x']
        msg.dropoff_location.y = self.stations[data.end_node]['y']
        
        self.publisher_.publish(msg)
        self.get_logger().info(f"📡 앱 호출 수신: {data.user_id} ({data.start_node} -> {data.end_node})")
        return True

# 3. FastAPI 앱 설정
app = FastAPI()
ros_node = None

@app.post("/call_taxi")
async def call_taxi(data: CallData):
    global ros_node
    success = ros_node.publish_ride(data)
    if success:
        return {"status": "success", "message": f"Taxi dispatched for {data.user_id}"}
    else:
        raise HTTPException(status_code=400, detail="Invalid Station ID")

# 4. 메인 실행 (ROS와 서버를 동시에 돌림)
def main():
    global ros_node
    rclpy.init()
    ros_node = RidePublisher()
    
    # ROS 2는 별도 스레드에서 돔 (Non-blocking)
    spin_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    spin_thread.start()
    
    print("🚀 [서버 시작] 앱에서 접속 가능: http://0.0.0.0:8000")
    # 웹 서버 실행 (0.0.0.0은 외부 접속 허용)
    uvicorn.run(app, host="0.0.0.0", port=8000)

    ros_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
