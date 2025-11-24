/*
 * obstacle_avoider.cpp (F1Tenth LiDAR 버전)
 * LiDAR (/scan) 토픽을 구독하여 장애물을 감지하고,
 * Ackermann (/drive) 토픽으로 조향각과 속도를 발행합니다.
 */

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"       // LiDAR 센서 메시지
#include "ackermann_msgs/msg/ackermann_drive_stamped.hpp" // F1Tenth 제어 메시지
#include <memory>
#include <vector>
#include <cmath>

// using 선언
using std::placeholders::_1;

class ObstacleAvoiderNode : public rclcpp::Node
{
public:
  ObstacleAvoiderNode() : Node("obstacle_avoider_node")
  {
    // 1. Publisher 생성
    // '/drive' 토픽으로 'AckermannDriveStamped' 메시지를 발행합니다.
    publisher_ = this->create_publisher<ackermann_msgs::msg::AckermannDriveStamped>("/sim/drive", 10);

    // 2. Subscriber 생성
    // '/scan' 토픽을 구독하고, 메시지가 오면 'scan_callback' 함수를 실행합니다.
    subscription_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
      "/sim/scan", 
      rclcpp::SensorDataQoS(), // QoS 설정 (센서 데이터에 최적화)
      std::bind(&ObstacleAvoiderNode::scan_callback, this, _1));

    RCLCPP_INFO(this->get_logger(), "F1Tenth 장애물 회피 노드가 시작되었습니다.");
  }

private:
  // LiDAR 스캔 콜백 함수 (핵심 로직)
  void scan_callback(const sensor_msgs::msg::LaserScan::SharedPtr msg)
  {
    // 제어 명령을 담을 새 메시지 생성
    auto drive_msg = ackermann_msgs::msg::AckermannDriveStamped();

    // --- 1. 인지 (Perception) ---
    // F1Tenth LiDAR는 1080개의 스캔 포인트가 있습니다.
    // 정면(540), 왼쪽 45도(810), 오른쪽 45도(270)의 거리 값을 확인합니다.
    // (LiDAR가 거꾸로 달려있을 수 있으므로 인덱스가 다를 수 있으나, F1Tenth Gym은 540이 정면입니다)
    
    // 1080개 포인트 중 유효한 값만 골라서 평균을 낼 수도 있습니다.
    // 여기서는 간단하게 3개의 포인트만 봅니다.
    // msg->ranges[] 배열에 1080개의 거리(미터) 값이 들어있습니다.
    
    float forward_dist = msg->ranges[540]; // 정면
    float left_dist    = msg->ranges[810]; // 왼쪽 45도
    float right_dist   = msg->ranges[270]; // 오른쪽 45도

    // --- 2. 판단 (Decision) ---
    const float SAFETY_THRESHOLD = 3.0; // 3.0 미터
    float target_steering = 0.0;    // 목표 조향각 (라디안)
    float target_speed = 1.5;       // 목표 속도 (m/s)

    if (std::isnan(forward_dist)) {
        forward_dist = SAFETY_THRESHOLD; // 유효하지 않은 값이면 안전하다고 가정
    }
    if (std::isnan(left_dist)) {
        left_dist = 0.0;
    }
    if (std::isnan(right_dist)) {
        right_dist = 0.0;
    }

    if (forward_dist < SAFETY_THRESHOLD)
    {
      // [판단] 정면이 위험하다!
      RCLCPP_WARN(this->get_logger(), "전방 장애물 감지! (%.2f m)", forward_dist);
      
      // [판단] 왼쪽과 오른쪽 중 어디가 더 '넓은가'?
      if (left_dist > right_dist)
      {
        // 왼쪽이 더 넓으니, 왼쪽으로 튼다 (조향각 -0.5)
        target_steering = -0.5; // (F1Tenth Gym에서는 음수가 왼쪽)
        RCLCPP_INFO(this->get_logger(), "왼쪽으로 회피!");
      }
      else
      {
        // 오른쪽이 더 넓으니, 오른쪽으로 튼다 (조향각 +0.5)
        target_steering = 0.5; // (양수가 오른쪽)
        RCLCPP_INFO(this->get_logger(), "오른쪽으로 회피!");
      }
      // 장애물 감지 시 속도 감속
      target_speed = 0.5;
    }
    else
    {
      // [판단] 정면이 안전하다. -> [제어] 직진
      target_steering = 0.0;
      target_speed = 1.5;
    }

    // --- 3. 제어 (Action) ---
    drive_msg.drive.steering_angle = target_steering;
    drive_msg.drive.speed = target_speed;

    // 최종적으로 계산된 제어 명령을 발행(Publish)합니다.
    publisher_->publish(drive_msg);
  }

  // --- 멤버 변수 선언 ---
  rclcpp::Publisher<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr publisher_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr subscription_;
};

// --- C++ 프로그램의 시작점 ---
int main(int argc, char * argv[])
{
  // ROS 2 초기화
  rclcpp::init(argc, argv);
  // 'ObstacleAvoiderNode'의 인스턴스를 만들고, 노드를 'spin' (실행 대기) 상태로 둡니다.
  rclcpp::spin(std::make_shared<ObstacleAvoiderNode>());
  // 노드가 종료되면 ROS 2 종료
  rclcpp::shutdown();
  return 0;
}
