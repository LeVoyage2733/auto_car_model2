#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "ackermann_msgs/msg/ackermann_drive_stamped.hpp"
#include <memory>
#include <vector>
#include <cmath>

using std::placeholders::_1;

class WallFollowerNode : public rclcpp::Node
{
public:
  WallFollowerNode() : Node("wall_follower_node")
  {
    // �controlling order Publisher
    publisher_ = this->create_publisher<ackermann_msgs::msg::AckermannDriveStamped>("/sim/drive", 10);

    // LiDAR �sensor Publisher
    subscription_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
      "/sim/scan",
      rclcpp::SensorDataQoS(),
      std::bind(&WallFollowerNode::scan_callback, this, _1));
      
    RCLCPP_INFO(this->get_logger(), "Wall Follower (P-Controller) 노드가 시작되었습니다.");
  }

private:
  // LiDAR Scan CallBack function
  void scan_callback(const sensor_msgs::msg::LaserScan::SharedPtr msg)
  {
    // --- 1. Perception ---
    // LiDAR (1080개)의 왼쪽 90도(810), 오른쪽 90도(270) 인덱스의 거리를 가져옵니다.
    // (이 인덱스는 차량의 설치 방향에 따라 튜닝이 필요할 수 있습니다.)
    float left_dist = msg->ranges[780];
    float right_dist = msg->ranges[300];

    // 유효하지 않은 값(inf, nan) 처리
    if (std::isinf(left_dist) || std::isnan(left_dist)) {
        left_dist = 10.0; // 벽이 없으면 10미터로 가정
    }
    if (std::isinf(right_dist) || std::isnan(right_dist)) {
        right_dist = 10.0; // 벽이 없으면 10미터로 가정
    }

    // --- 2. 판단 (Planning) - P 제어 ---
    
    // 목표: 왼쪽 거리와 오른쪽 거리의 차이(Error)를 0으로 만든다.
    float error = left_dist - right_dist;
    
    // P-제어기 상수 (이 값을 튜닝하면서 최적의 주행을 찾아야 합니다!)
    const double Kp = 0.08; // 비례 상수 (클수록 핸들을 날카롭게 꺾음)

    // --- 3. 제어 (Action) ---
    auto drive_msg = ackermann_msgs::msg::AckermannDriveStamped();
    
    // steering_angle = Kp * error
    // (F1Tenth Gym에서는 음수가 왼쪽, 양수가 오른쪽 핸들 조작)
    // 에러가 양수(오른쪽에 가까움) -> 핸들을 왼쪽(음수)으로 꺾어야 함.
    // 따라서 -Kp를 곱해줍니다.
    drive_msg.drive.steering_angle = -Kp * error;

    // 속도는 고정 (나중에는 에러 값에 따라 속도를 줄일 수도 있습니다)
    drive_msg.drive.speed = 3.0; // m/s (너무 빠르면 제어가 안됨)
    
    RCLCPP_INFO(this->get_logger(), "L:%.2f, R:%.2f, Err:%.2f, Steer:%.2f", 
                left_dist, right_dist, error, drive_msg.drive.steering_angle);

    publisher_->publish(drive_msg);
  }

  rclcpp::Publisher<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr publisher_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr subscription_;
};

// --- C++ 프로그램의 시작점 ---
int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<WallFollowerNode>());
  rclcpp::shutdown();
  return 0;
}
