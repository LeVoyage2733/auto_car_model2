#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import yaml
import time
import os
from ride_service_interfaces.msg import RideRequest

class RideDispatcher(Node):
    def __init__(self):
        super().__init__('ride_dispatcher')
        self.publisher_ = self.create_publisher(RideRequest, '/ride_request', 10)
        self.yaml_path = 'requests.yaml'  # 실행 위치에 파일이 있어야 함
        self.timer = self.create_timer(1.0, self.check_yaml)  # 1초마다 파일 확인
        self.get_logger().info("🚕 배차 시스템(Dispatcher) 가동 중... YAML 파일을 감시합니다.")

    def check_yaml(self):
        if not os.path.exists(self.yaml_path):
            return

        try:
            with open(self.yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data or 'requests' not in data:
                return

            updated = False
            for user_id, info in data['requests'].items():
                # 상태가 'new'인 요청만 처리
                if info['status'] == 'new':
                    msg = RideRequest()
                    msg.pickup_location.x = float(info['pickup']['x'])
                    msg.pickup_location.y = float(info['pickup']['y'])
                    msg.dropoff_location.x = float(info['dropoff']['x'])
                    msg.dropoff_location.y = float(info['dropoff']['y'])

                    self.publisher_.publish(msg)
                    self.get_logger().info(f"📢 호출 발송: {user_id} -> 픽업({msg.pickup_location.x}, {msg.pickup_location.y})")
                    
                    # 상태를 'dispatched'로 변경하여 중복 발송 방지
                    data['requests'][user_id]['status'] = 'dispatched'
                    updated = True

            # 상태가 변경되었으면 파일에 다시 저장
            if updated:
                with open(self.yaml_path, 'w') as f:
                    yaml.dump(data, f)

        except Exception as e:
            self.get_logger().error(f"파일 읽기 오류: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = RideDispatcher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
