/*
 * wall_avoider.cpp (버그 수정본)
 * [수정] 모든 '판단' 로직을 timer_callback으로 옮겨서 상태 머신 오류를 해결합니다.
 */

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp" // 속도 명령 (발행)
#include "turtlesim/msg/pose.hpp"      // 거북이 위치 (구독)
#include <memory>
#include <cmath>

// using 선언으로 코드를 간결하게 만듭니다.
using std::placeholders::_1;

// 'rclcpp::Node'를 상속받아 'WallAvoiderNode' 클래스를 정의합니다.
class WallAvoiderNode : public rclcpp::Node
{
public:
  // 노드 생성자
  WallAvoiderNode() : Node("wall_avoider_node"), state_(State::MOVING_STRAIGHT)
  {
    // 1. Publisher 생성
    publisher_ = this->create_publisher<geometry_msgs::msg::Twist>("/turtle1/cmd_vel", 10);

    // 2. Subscriber 생성
    // [수정!] 콜백은 오직 현재 위치를 '저장'하는 역할만 합니다.
    subscription_ = this->create_subscription<turtlesim::msg::Pose>(
      "/turtle1/pose", 10, std::bind(&WallAvoiderNode::pose_callback, this, _1));

    // 3. Timer 생성 (메인 컨트롤 루프)
    timer_ = this->create_wall_timer(
      std::chrono::milliseconds(100), std::bind(&WallAvoiderNode::timer_callback, this));

    RCLCPP_INFO(this->get_logger(), "'wall_avoider_node'가 시작되었습니다. (버그 수정본)");

    // current_pose_가 초기화될 때까지 잠시 대기 (선택 사항이지만 안전함)
    // current_pose_.x = -1.0; // 초기값을 -1로 설정하여 유효한지 확인할 수 있음
  }

private:
  // 거북이의 현재 상태 (직진 중인지, 회전 중인지)
  enum class State
  {
    MOVING_STRAIGHT,
    TURNING
  };

  // [수정된 pose_callback]
  // 판단 로직을 모두 제거하고, 오직 'current_pose_' 변수에 최신 위치를 저장만 합니다.
  void pose_callback(const turtlesim::msg::Pose::SharedPtr msg)
  {
    current_pose_ = *msg;
  }

  // [수정된 timer_callback]
  // 0.1초마다 호출되는 메인 제어 루프. 모든 '판단'과 '제어'를 여기서 수행합니다.
  void timer_callback()
  {
    auto twist_msg = geometry_msgs::msg::Twist(); // 보낼 메시지 생성
    
    // [판단 로직 추가] 0.1초마다 현재 위치를 기준으로 벽 충돌을 '판단'합니다.
    const double border_threshold = 1.0; // 벽에서 1.0미터
    bool too_close_to_wall = 
      current_pose_.x < border_threshold || 
      current_pose_.x > 11.08 - border_threshold ||
      current_pose_.y < border_threshold ||
      current_pose_.y > 11.08 - border_threshold;

    // --- 상태 머신 로직 ---
    if (state_ == State::MOVING_STRAIGHT)
    {
      // [직진 상태]
      if (too_close_to_wall)
      {
        // 1. [판단] 벽에 부딪혔다!
        RCLCPP_WARN(this->get_logger(), "벽 감지! (x=%.2f, y=%.2f). 회전을 시작합니다.", current_pose_.x, current_pose_.y);
        state_ = State::TURNING; // 2. [상태 변경] '회전'으로 변경
        turn_start_time_ = this->get_clock()->now(); // 3. 회전 시작 시간 기록

        // 4. [제어] 즉시 회전 명령
        twist_msg.linear.x = 0.0;
        twist_msg.angular.z = 1.0; // 반시계 방향 회전
      }
      else
      {
        // [판단] 벽에 안 부딪혔다 -> [제어] 계속 직진
        twist_msg.linear.x = 1.0;
        twist_msg.angular.z = 0.0;
      }
    }
    else // state_ == State::TURNING
    {
      // [회전 상태]
      // 1. [판단] 1초가 지났는지 확인
      if ((this->get_clock()->now() - turn_start_time_).seconds() > 1.0)
      {
        RCLCPP_INFO(this->get_logger(), "회전 완료. 다시 직진을 시작합니다.");
        state_ = State::MOVING_STRAIGHT; // 2. [상태 변경] '직진'으로 변경
        
        // 3. [제어] 즉시 직진 명령
        twist_msg.linear.x = 1.0;
        twist_msg.angular.z = 0.0;
      }
      else
      {
        // 1. [판단] 1초가 안 지났다 -> [제어] 계속 회전
        twist_msg.linear.x = 0.0;
        twist_msg.angular.z = 1.0;
      }
    }
    
    // 최종적으로 계산된 속도 명령을 발행(Publish)합니다.
    publisher_->publish(twist_msg);
  }

  // --- 멤버 변수 선언 ---
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr publisher_;
  rclcpp::Subscription<turtlesim::msg::Pose>::SharedPtr subscription_;
  rclcpp::TimerBase::SharedPtr timer_;
  turtlesim::msg::Pose current_pose_; // 현재 거북이 위치 저장
  State state_; // 현재 거북이 상태 (직진/회전)
  rclcpp::Time turn_start_time_{0, 0, this->get_clock()->get_clock_type()}; // 회전 시작 시간
};

// --- C++ 프로그램의 시작점 (수정 필요 없음) ---
int main(int argc, char * argv[])
{
  // ROS 2 초기화
  rclcpp::init(argc, argv);
  // 'WallAvoiderNode'의 인스턴스를 만들고, 노드를 'spin' (실행 대기) 상태로 둡니다.
  rclcpp::spin(std::make_shared<WallAvoiderNode>());
  // 노드가 종료되면 ROS 2 종료
  rclcpp::shutdown();
  return 0;
}
