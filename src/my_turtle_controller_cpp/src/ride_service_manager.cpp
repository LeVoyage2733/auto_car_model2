#include "rclcpp/rclcpp.hpp"
#include <chrono>
#include <cmath>
#include <algorithm>
#include <vector>
#include <clocale>

#include "ride_service_interfaces/msg/ride_request.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "ackermann_msgs/msg/ackermann_drive_stamped.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "nav_msgs/msg/path.hpp" 
#include "visualization_msgs/msg/marker.hpp"

using std::placeholders::_1;
using namespace std::chrono_literals;

struct Waypoint { double x; double y; };
enum class State { IDLE, WAITING_FOR_PATH, FOLLOWING_PATH, AT_PICKUP, MISSION_COMPLETE };

class RideServiceManager : public rclcpp::Node {
public:
    RideServiceManager() : Node("ride_service_manager") {
        RCLCPP_INFO(this->get_logger(), ">>> AI Taxi (A* Path Follower) Ready! <<<");

        // 1. 통신 설정
        request_sub_ = this->create_subscription<ride_service_interfaces::msg::RideRequest>(
            "/ride_request", 10, std::bind(&RideServiceManager::request_callback, this, _1));

        // [핵심] 파이썬 플래너가 계산한 경로를 받습니다.
        path_sub_ = this->create_subscription<nav_msgs::msg::Path>(
            "/planned_path", 10, std::bind(&RideServiceManager::path_callback, this, _1));

        odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
            "/ego_racecar/odom", 10, std::bind(&RideServiceManager::odom_callback, this, _1));

        drive_pub_ = this->create_publisher<ackermann_msgs::msg::AckermannDriveStamped>("/drive", 10);
        target_pub_ = this->create_publisher<visualization_msgs::msg::Marker>("/target_marker", 10);

        // 2. 좌표 설정 (앱과 동일해야 함)
        geometry_msgs::msg::Point p;
        // (좌표는 앱에서 오는 요청을 믿으므로 여기서는 초기화만 함)
        
        timer_ = this->create_wall_timer(50ms, std::bind(&RideServiceManager::control_loop, this));
    }

private:
    std::vector<Waypoint> dynamic_path_; // A*가 준 경로 저장소
    int current_path_idx_ = 0;

    // 경로 수신 콜백 (파이썬 -> C++)
    void path_callback(const nav_msgs::msg::Path::SharedPtr msg) {
        dynamic_path_.clear();
        for (const auto& pose : msg->poses) {
            Waypoint wp;
            wp.x = pose.pose.position.x;
            wp.y = pose.pose.position.y;
            dynamic_path_.push_back(wp);
        }
        current_path_idx_ = 0;
        state_ = State::FOLLOWING_PATH;
        RCLCPP_INFO(this->get_logger(), "📥 경로 수신! 주행 시작 (총 %lu 개 지점)", dynamic_path_.size());
    }

    void request_callback(const ride_service_interfaces::msg::RideRequest::SharedPtr msg) {
        if (state_ == State::IDLE || state_ == State::MISSION_COMPLETE) {
            RCLCPP_INFO(this->get_logger(), "🔔 호출 수신! 경로 계산 대기 중...");
            dropoff_loc_ = msg->dropoff_location; // 목적지 저장
            state_ = State::WAITING_FOR_PATH;
            // (참고: 실제 경로 계산 요청은 ride_dispatcher나 global_planner가 토픽을 보고 알아서 수행함)
        }
    }

    void odom_callback(const nav_msgs::msg::Odometry::SharedPtr msg) {
        current_x_ = msg->pose.pose.position.x;
        current_y_ = msg->pose.pose.position.y;
        
        double qx = msg->pose.pose.orientation.x;
        double qy = msg->pose.pose.orientation.y;
        double qz = msg->pose.pose.orientation.z;
        double qw = msg->pose.pose.orientation.w;
        double siny_cosp = 2.0 * (qw * qz + qx * qy);
        double cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz);
        current_yaw_ = std::atan2(siny_cosp, cosy_cosp);
    }

    double get_dist(double x1, double y1, double x2, double y2) {
        return std::sqrt(std::pow(x1 - x2, 2) + std::pow(y1 - y2, 2));
    }

    void control_loop() {
        ackermann_msgs::msg::AckermannDriveStamped drive_msg;
        drive_msg.header.stamp = this->get_clock()->now();
        drive_msg.header.frame_id = "base_link";
        
        double steering_angle = 0.0;
        double speed = 0.0;

        if (state_ == State::FOLLOWING_PATH && !dynamic_path_.empty()) {
            // [튜닝] 전방 주시 거리 (벽 뚫기 방지: 짧게 설정)
            double lookahead_dist = 0.8; 
            
            // 현재 위치에서 L 거리만큼 떨어진 점 찾기 (순차 탐색)
            bool found_target = false;
            for (size_t i = current_path_idx_; i < dynamic_path_.size(); i++) {
                double d = get_dist(current_x_, current_y_, dynamic_path_[i].x, dynamic_path_[i].y);
                if (d > lookahead_dist) {
                    current_path_idx_ = i; // 다음엔 여기서부터 찾음 (효율성)
                    found_target = true;
                    break;
                }
            }
            
            // 경로 끝에 도달했을 때
            if (!found_target) {
                current_path_idx_ = dynamic_path_.size() - 1;
            }

            Waypoint target = dynamic_path_[current_path_idx_];
            publish_target_marker(target);

            // Pure Pursuit 조향 계산
            double dx = target.x - current_x_;
            double dy = target.y - current_y_;
            double local_y = std::sin(-current_yaw_) * dx + std::cos(-current_yaw_) * dy;
            double curvature = 2.0 * local_y / (lookahead_dist * lookahead_dist);
            
            steering_angle = curvature;
            
            // [튜닝] 속도 설정 (벽 뚫기 방지: 속도 줄임)
            // 코너(조향각이 클 때)에서는 더 천천히
            if (std::abs(steering_angle) > 0.2) {
                speed = 1.0; // 코너링 속도
            } else {
                speed = 2.0; // 직선 속도
            }

            // [정차 로직] 경로의 마지막 점과 가까워지면 정지
            Waypoint final_wp = dynamic_path_.back();
            double dist_to_goal = get_dist(current_x_, current_y_, final_wp.x, final_wp.y);
            
            if (dist_to_goal < 1.0) { // 1m 이내 도착 시
                speed = 0.0;
                RCLCPP_INFO(this->get_logger(), "🏁 목적지 도착! (미션 완료)");
                state_ = State::IDLE;
                dynamic_path_.clear(); // 경로 삭제 (재출발 방지)
            }
        }

        // 조향각 제한 (-0.4 ~ 0.4 rad)
        drive_msg.drive.steering_angle = std::max(-0.4, std::min(0.4, steering_angle));
        drive_msg.drive.speed = speed;
        drive_pub_->publish(drive_msg);
    }

    void publish_target_marker(Waypoint target) {
        visualization_msgs::msg::Marker marker;
        marker.header.frame_id = "map";
        marker.header.stamp = this->get_clock()->now();
        marker.ns = "target";
        marker.id = 1;
        marker.type = visualization_msgs::msg::Marker::SPHERE;
        marker.action = visualization_msgs::msg::Marker::ADD;
        marker.pose.position.x = target.x;
        marker.pose.position.y = target.y;
        marker.pose.position.z = 0.5;
        marker.scale.x = 0.5; marker.scale.y = 0.5; marker.scale.z = 0.5;
        marker.color.r = 1.0f; marker.color.a = 1.0;
        target_pub_->publish(marker);
    }

    rclcpp::Subscription<ride_service_interfaces::msg::RideRequest>::SharedPtr request_sub_;
    rclcpp::Subscription<nav_msgs::msg::Path>::SharedPtr path_sub_;
    rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
    rclcpp::Publisher<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr drive_pub_;
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr target_pub_;

    rclcpp::TimerBase::SharedPtr timer_;
    State state_ = State::IDLE;
    geometry_msgs::msg::Point dropoff_loc_;
    double current_x_ = 0.0, current_y_ = 0.0, current_yaw_ = 0.0;
};

int main(int argc, char * argv[]) {
    std::setlocale(LC_NUMERIC, "C");
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<RideServiceManager>());
    rclcpp::shutdown();
    return 0;
}
