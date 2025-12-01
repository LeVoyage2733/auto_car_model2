import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import asyncio
import websockets

# 1. ROS 2 노드 정의 (데이터를 쏘는 역할)
class BusBridgeNode(Node):
    def __init__(self):
        super().__init__('web_to_ros_bridge')
        
        # 'reservation_call'이라는 이름의 토픽으로 방송합니다.
        # 다른 자율주행 노드들은 이 토픽을 구독(Subscribe)하면 됩니다.
        self.publisher_ = self.create_publisher(String, 'reservation_call', 10)
        self.get_logger().info('✅ [ROS 2] Web Bridge Node가 시작되었습니다.')

    def publish_reservation(self, data):
        msg = String()
        msg.data = data
        self.publisher_.publish(msg)
        self.get_logger().info(f'📢 [Topic 발행] reservation_call: "{data}"')

# 2. 웹소켓 리스너 (서버에서 듣는 역할)
async def listen_to_server(ros_node):
    # ★ 도커에서 윈도우(FastAPI)를 찾는 주소
    uri = "ws://host.docker.internal:8000/ws/vehicle/Bus01"
    
    while True:
        try:
            print(f"🤖 [연결 시도] 서버({uri}) 찾는 중...")
            async with websockets.connect(uri) as websocket:
                print("✅ 서버 연결 성공! 예약 대기 중...")
                
                while True:
                    # 서버에서 메시지가 올 때까지 대기 (Blocking)
                    message = await websocket.recv()
                    
                    # 메시지 도착! -> ROS 2 토픽으로 쏘기
                    print(f"📩 [서버 수신] {message}")
                    ros_node.publish_reservation(message)
                    
        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError):
            print("⚠️ 서버 연결이 끊겼거나 켜져있지 않습니다. 3초 후 재시도...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            await asyncio.sleep(3)

# 3. 메인 실행부
def main():
    rclpy.init()
    node = BusBridgeNode()
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(listen_to_server(node))
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()