// C++ ROS 2 핵심 헤더
#include "rclcpp/rclcpp.hpp"
// 우리가 사용할 Twist 메시지 헤더
#include "geometry_msgs/msg/twist.hpp"
// 100ms 같은 시간 단위를 사용하기 위한 헤더
#include "chrono"

// 'using' 키워드로 코드를 간결하게 만듭니다.
using namespace std::chrono_literals;

// rclcpp::Node를 상속받아 DrawSquareNode 클래스를 정의합니다.
class DrawSquareNode : public rclcpp::Node
{
public:
  // 생성자
  DrawSquareNode()
  : Node("draw_square_node"), state_("MOVING_STRAIGHT"), state_timer_(0.0)
  {
    // '/turtle1/cmd_vel' 토픽에 Twist 메시지를 발행하는 퍼블리셔 생성
    publisher_ = this->create_publisher<geometry_msgs::msg::Twist>("/turtle1/cmd_vel", 10);
    
    // 0.1초(100ms)마다 timer_callback 함수를 호출하는 타이머 생성
    // std::bind를 사용해 클래스 멤버 함수를 콜백으로 등록
    timer_ = this->create_wall_timer(
      100ms, std::bind(&DrawSquareNode::timer_callback, this));
      
    RCLCPP_INFO(this->get_logger(), "거북이 사각형 그리기 노드(C++) 시작!");
  }

private:
  // 타이머 콜백 함수
  void timer_callback()
  {
    // C++에서는 'auto' 키워드로 메시지 타입을 자동 추론할 수 있습니다.
    auto msg = geometry_msgs::msg::Twist();

    // 1. 현재 상태가 '직진'일 때
    if (state_ == "MOVING_STRAIGHT")
    {
      msg.linear.x = 1.0; // 초당 1.0 미터 속도로 직진
      
      // 2초가 지났는지 확인
      if (state_timer_ >= 2.0)
      {
        state_ = "TURNING";     // 상태를 '회전'으로 변경
        state_timer_ = 0.0;     // 상태 타이머 초기화
        RCLCPP_INFO(this->get_logger(), "직진 완료. 회전을 시작합니다.");
      }
    }
    // 2. 현재 상태가 '회전'일 때
    else if (state_ == "TURNING")
    {
      msg.angular.z = 1.57; // 초당 1.57 라디안 (약 90도) 속도로 회전
      
      // 1초가 지났는지 확인
      if (state_timer_ >= 1.0)
      {
        state_ = "MOVING_STRAIGHT"; // 상태를 '직진'으로 변경
        state_timer_ = 0.0;         // 상태 타이머 초기화
        RCLCPP_INFO(this->get_logger(), "회전 완료. 직진을 시작합니다.");
      }
    }

    // 퍼블리셔로 메시지 발행
    publisher_->publish(msg);
    
    // 상태 타이머 갱신 (0.1초 증가)
    state_timer_ += 0.1;
  }

  // 클래스 멤버 변수 선언
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr publisher_;
  std::string state_;
  double state_timer_;
};

// C++ 프로그램의 메인 함수
int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv); // ROS 2 초기화
  
  // DrawSquareNode의 인스턴스를 생성하고, 노드가 종료될 때까지 대기(spin)
  rclcpp::spin(std::make_shared<DrawSquareNode>());
  
  rclcpp::shutdown(); // ROS 2 종료
  return 0;
}
