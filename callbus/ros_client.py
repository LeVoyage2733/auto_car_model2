import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import asyncio
import websockets

class BusBridgeNode(Node):
    def __init__(self):
        super().__init__('web_to_ros_bridge')
        self.publisher_ = self.create_publisher(String, 'reservation_call', 10)
        self.get_logger().info('✅ [ROS 2] Web Bridge Node Started')

    def publish_reservation(self, data):
        msg = String()
        msg.data = data
        self.publisher_.publish(msg)
        self.get_logger().info(f'📢 [Send] {data}')

async def listen_to_server(ros_node):
    # 도커 -> 윈도우 접속 주소
    uri = "ws://host.docker.internal:8000/ws/vehicle/Bus01"
    
    while True:
        try:
            print(f"🤖 Connecting to {uri}...")
            async with websockets.connect(uri) as websocket:
                print("✅ Connected! Waiting for reservation...")
                while True:
                    message = await websocket.recv()
                    print(f"📩 [Received] {message}")
                    ros_node.publish_reservation(message)
        except Exception as e:
            print(f"⚠️ Connection failed (Retrying in 3s)... Error: {e}")
            await asyncio.sleep(3)

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
