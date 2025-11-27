#include "rclcpp/rclcpp.hpp"
#include <chrono>
#include <cmath>
#include <algorithm>
#include <vector>
#include <clocale>

#include "ride_service_interfaces/msg/ride_request.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "ackermann_msgs/msg/ackermann_drive_stamped.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
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
        RCLCPP_INFO(this->get_logger(), ">>> 안전 운전 AI Taxi 시작! <<<");

        request_sub_ = this->create_subscription<ride_service_interfaces::msg::RideRequest>(
            "/ride_request", 10, std::bind(&RideServiceManager::request_callback, this, _1));
        path_sub_ = this->create_subscription<nav_msgs::msg::Path>(
            "/planned_path", 10, std::bind(&RideServiceManager::path_callback, this, _1));
        odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
            "/ego_racecar/odom", 10, std::bind(&RideServiceManager::odom_callback, this, _1));
        scan_sub_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
            "/scan", rclcpp::SensorDataQoS(), std::bind(&RideServiceManager::scan_callback, this, _1));

        drive_pub_ = this->create_publisher<ackermann_msgs::msg::AckermannDriveStamped>("/drive", 10);
        marker_pub_ = this->create_publisher<visualization_msgs::msg::Marker>("/path_marker", 10);
        target_pub_ = this->create_publisher<visualization_msgs::msg::Marker>("/target_marker", 10);

        timer_ = this->create_wall_timer(50ms, std::bind(&RideServiceManager::control_loop, this));
    }

private:
    std::vector<Waypoint> dynamic_path_;
    int current_path_idx_ = 0;
    float front_dist_ = 10.0; // 전방 장애물 거리

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
        RCLCPP_INFO(this->get_logger(), "📥 경로 수신! 안전 운전 모드 시작.");
        publish_path_marker();
    }

    void request_callback(const ride_service_interfaces::msg::RideRequest::SharedPtr msg) {
        if (state_ == State::IDLE || state_ == State::MISSION_COMPLETE) {
            RCLCPP_INFO(this->get_logger(), "🔔 호출 수신! 대기 중...");
            state_ = State::WAITING_FOR_PATH;
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

    void scan_callback(const sensor_msgs::msg::LaserScan::SharedPtr msg) {
        // 정면(540번 빔) 근처의 거리 평균값 사용 (안전장치)
        int center_idx = 540; 
        if (center_idx < msg->ranges.size()) {
            front_dist_ = msg->ranges[center_idx];
        }
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
            // [튜닝 1] 전방 주시 거리 (Lookahead)
            // 유턴이나 급커브에서는 짧게 봐아야 안쪽으로 파고듦
            double lookahead_dist = 0.7; 
            
            // 현재 위치에서 가까운 경로점 찾기
            bool found_target = false;
            for (size_t i = current_path_idx_; i < dynamic_path_.size(); i++) {
                double d = get_dist(current_x_, current_y_, dynamic_path_[i].x, dynamic_path_[i].y);
                if (d > lookahead_dist) {
                    current_path_idx_ = i; 
                    found_target = true;
                    break;
                }
            }
            if (!found_target) current_path_idx_ = dynamic_path_.size() - 1;

            Waypoint target = dynamic_path_[current_path_idx_];
            publish_target_marker(target);

            double dx = target.x - current_x_;
            double dy = target.y - current_y_;
            double local_y = std::sin(-current_yaw_) * dx + std::cos(-current_yaw_) * dy;
            double curvature = 2.0 * local_y / (lookahead_dist * lookahead_dist);
            
            steering_angle = curvature;
            
            // [튜닝 2] 속도 제어 (코너링 & 유턴 시 감속)
            if (std::abs(steering_angle) > 0.3) {
                speed = 0.5; // 급커브: 기어가기
            } else if (std::abs(steering_angle) > 0.15) {
                speed = 1.0; // 일반 커브
            } else {
                speed = 2.5; // 직선: 빠르게
            }

            // [튜닝 3] 긴급 정지 (벽 뚫기 방지 최후의 수단)
            if (front_dist_ < 0.5) {
                // 앞에 벽이 있으면 멈추거나 후진(선택)
                speed = 0.0; 
                // (후진 기능이 필요하면 speed = -0.5; 로 설정)
            }

            // 도착 판정
            Waypoint final_wp = dynamic_path_.back();
            if (get_dist(current_x_, current_y_, final_wp.x, final_wp.y) < 1.0) {
                speed = 0.0;
                RCLCPP_INFO(this->get_logger(), "🏁 도착 완료!");
                state_ = State::IDLE;
                dynamic_path_.clear(); 
            }
        }

        drive_msg.drive.steering_angle = std::max(-0.4, std::min(0.4, steering_angle));
        drive_msg.drive.speed = speed;
        drive_pub_->publish(drive_msg);
        
        publish_path_marker();
    }

    void publish_path_marker() {
        visualization_msgs::msg::Marker points;
        points.header.frame_id = "map";
        points.ns = "path";
        points.action = visualization_msgs::msg::Marker::ADD;
        points.id = 0;
        points.type = visualization_msgs::msg::Marker::POINTS;
        points.scale.x = 0.1; points.scale.y = 0.1;
        points.color.g = 1.0f; points.color.a = 1.0;
        for (const auto& wp : dynamic_path_) {
            geometry_msgs::msg::Point p; p.x = wp.x; p.y = wp.y;
            points.points.push_back(p);
        }
        marker_pub_->publish(points);
    }

    void publish_target_marker(Waypoint target) {
        visualization_msgs::msg::Marker marker;
        marker.header.frame_id = "map";
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
    rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
    rclcpp::Publisher<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr drive_pub_;
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr marker_pub_;
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr target_pub_; 

    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::TimerBase::SharedPtr one_shot_timer_;
    State state_ = State::IDLE;
    double current_x_ = 0.0, current_y_ = 0.0, current_yaw_ = 0.0;
};

int main(int argc, char * argv[]) {
    std::setlocale(LC_NUMERIC, "C");
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<RideServiceManager>());
    rclcpp::shutdown();
    return 0;
}
