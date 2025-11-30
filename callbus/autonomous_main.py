import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class AutonomousCar(Node):
    def __init__(self):
        super().__init__('autonomous_car')
        
        # [변수 선언]
        self.destination = "없음"
        self.is_moving = False

        # [구독 설정] 아까 만든 ros_client.py가 보내는 걸 듣습니다.
        self.subscription = self.create_subscription(
            String,
            '/reservation_call',  # 토픽 이름
            self.update_destination, # 데이터 오면 실행할 함수
            10
        )
        
        # [주행 루프] 1초마다 주행 상태 체크
        self.timer = self.create_timer(1.0, self.drive_control)

    # [데이터 수신부]
    def update_destination(self, msg):
        # 데이터 파싱: "CALL:N-30,출발,도착"
        try:
            content = msg.data.split(":")[1] # "N-30,출발,도착"
            parts = content.split(",")       # ['N-30', '출발', '도착']
            
            # 변수에 저장 (전역변수 효과)
            self.destination = parts[2] 
            self.is_moving = True
            
            self.get_logger().info(f"📍 새 목적지 업데이트: {self.destination}")
            
        except IndexError:
            self.get_logger().error("데이터 형식이 이상합니다.")

    # [주행 제어부]
    def drive_control(self):
        if self.is_moving:
            # 여기에 실제 자율주행 코드를 넣으세요 (waypoint 설정 등)
            self.get_logger().info(f"엔진 가동! {self.destination}로 가는 중... 부릉부릉 🚗")
        else:
            self.get_logger().info("호출 대기 중... 💤")

def main(args=None):
    rclpy.init(args=args)
    car = AutonomousCar()
    rclpy.spin(car)
    car.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
