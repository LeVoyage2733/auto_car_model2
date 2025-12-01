import rclpy
from rclpy.node import Node
from ride_service_interfaces.msg import RideRequest
import websockets
import asyncio

# 정류장 좌표 (우리 맵 기준)
STATIONS = {
    1: {'x': 5.12, 'y': 16.0}, 2: {'x': 36.2, 'y': 27.7},
    3: {'x': 78.3, 'y': 14.2}, 4: {'x': 59.6, 'y': 61.9},
    5: {'x': 45.1, 'y': 57.9}, 6: {'x': 5.5, 'y': 54.1}
}

class WebToRosBridge(Node):
    def __init__(self):
        super().__init__('web_ros_bridge')
        self.publisher_ = self.create_publisher(RideRequest, '/ride_request', 10)
        self.get_logger().info("🌉 [Bridge] 준비 완료. WebSocket 연결 시도 중...")

    def publish_command(self, start_idx, end_idx, user_id):
        if start_idx not in STATIONS or end_idx not in STATIONS:
            self.get_logger().error(f"❌ 잘못된 정류장: {start_idx}->{end_idx}")
            return

        msg = RideRequest()
        msg.pickup_location.x = STATIONS[start_idx]['x']
        msg.pickup_location.y = STATIONS[start_idx]['y']
        msg.dropoff_location.x = STATIONS[end_idx]['x']
        msg.dropoff_location.y = STATIONS[end_idx]['y']

        self.publisher_.publish(msg)
        self.get_logger().info(f"🚀 [Bridge] ROS 명령 발송: {user_id} ({start_idx}->{end_idx})")

async def listen_to_web(node):
    # 친구 서버 주소 (같은 Docker 안이니까 localhost)
    uri = "ws://localhost:8000/ws/vehicle/Bus01"
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                node.get_logger().info(f"✅ 웹 서버 연결 성공!")
                while True:
                    # 서버가 방송하는 메시지 기다림
                    message = await websocket.recv()
                    node.get_logger().info(f"📩 [수신] {message}")
                    
                    # 메시지 해석 (CALL:user_id,start,end)
                    if message.startswith("CALL:"):
                        try:
                            parts = message.split(":")[1].split(",")
                            user_id = parts[0]
                            start = int(parts[1])
                            end = int(parts[2])
                            
                            # ROS 2 토픽 발행!
                            node.publish_command(start, end, user_id)
                        except Exception as e:
                            node.get_logger().error(f"메시지 오류: {e}")
        except Exception as e:
            node.get_logger().warn(f"⚠️ 서버 연결 실패 (3초 후 재시도)...")
            await asyncio.sleep(3)

def main(args=None):
    rclpy.init(args=args)
    node = WebToRosBridge()
    
    # 비동기 루프 실행
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(listen_to_web(node))
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
