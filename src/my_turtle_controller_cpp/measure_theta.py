import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
import math

class ThetaMeasurer(Node):
    def __init__(self):
        super().__init__('theta_measurer')
        # RViz의 2D Pose Estimate가 발행하는 토픽 구독
        self.subscription = self.create_subscription(
            PoseWithCovarianceStamped,
            '/initialpose',
            self.listener_callback,
            10)
        print("=== Theta 측정기 시작 ===")
        print("RViz에서 '2D Pose Estimate'로 화살표를 그려주세요.")

    def listener_callback(self, msg):
        # 쿼터니언 가져오기
        x = msg.pose.pose.orientation.x
        y = msg.pose.pose.orientation.y
        z = msg.pose.pose.orientation.z
        w = msg.pose.pose.orientation.w

        # 쿼터니언 -> 오일러(Yaw/Theta) 변환 공식
        # F1Tenth는 2D 평면이므로 Yaw만 계산하면 됨
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        theta_rad = math.atan2(t3, t4)
        
        theta_deg = math.degrees(theta_rad)

        print(f"\n[측정 결과]")
        print(f"------------------------------------------")
        print(f"👉 theta (라디안): {theta_rad:.4f}")  # 이 값을 yaml에 복사!
        print(f"   theta (도):     {theta_deg:.2f}도")
        print(f"------------------------------------------")

def main(args=None):
    rclpy.init(args=args)
    node = ThetaMeasurer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
