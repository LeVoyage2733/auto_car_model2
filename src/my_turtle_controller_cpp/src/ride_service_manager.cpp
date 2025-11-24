#include "rclcpp/rclcpp.hpp"
#include <chrono>
#include <cmath>
#include <algorithm>
#include <vector>
#include <fstream>
#include <sstream>
#include <string>
#include <clocale>

#include "ride_service_interfaces/msg/ride_request.hpp"
#include "geometry_msgs/msg/point.hpp"
#include "ackermann_msgs/msg/ackermann_drive_stamped.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "visualization_msgs/msg/marker.hpp"

using std::placeholders::_1;
using namespace std::chrono_literals;

const std::string CSV_PATH = "/home/misys/ros2_ws/src/my_turtle_controller_cpp/waypoints.csv";

struct Waypoint { double x; double y; };
enum class State { IDLE, GOING_TO_PICKUP, AT_PICKUP, GOING_TO_DROPOFF, MISSION_COMPLETE };

class RideServiceManager : public rclcpp::Node {
public:
    RideServiceManager() : Node("ride_service_manager") {
        RCLCPP_INFO(this->get_logger(), ">>> 스마트 Pure Pursuit 자율주행 시작! <<<");
        load_waypoints();
        
        request_sub_ = this->create_subscription<ride_service_interfaces::msg::RideRequest>("/ride_request", 10, std::bind(&RideServiceManager::request_callback, this, _1));
        odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>("/ego_racecar/odom", 10, std::bind(&RideServiceManager::odom_callback, this, _1));
        scan_sub_ = this->create_subscription<sensor_msgs::msg::LaserScan>("/scan", rclcpp::SensorDataQoS(), std::bind(&RideServiceManager::scan_callback, this, _1));
        
        drive_pub_ = this->create_publisher<ackermann_msgs::msg::AckermannDriveStamped>("/drive", 10);
        
        marker_pub_ = this->create_publisher<visualization_msgs::msg::Marker>("/path_marker", 10);
        target_pub_ = this->create_publisher<visualization_msgs::msg::Marker>("/target_marker", 10);

        geometry_msgs::msg::Point p;
        p.x = 3.32; p.y = 10.3; stations_.push_back(p);  
        p.x = 22.8; p.y = 16.5; stations_.push_back(p);  
        p.x = 49.1; p.y = 9.11; stations_.push_back(p);  
        p.x = 37.4; p.y = 38.6; stations_.push_back(p); 
        p.x = 3.44; p.y = 33.7; stations_.push_back(p); 
        target_loc_ = stations_[0];

        timer_ = this->create_wall_timer(50ms, std::bind(&RideServiceManager::control_loop, this));
        
        publish_path_marker();
    }

private:
    std::vector<Waypoint> global_path_;
    std::vector<geometry_msgs::msg::Point> stations_; // 여기에 딱 한 번만 선언됨!
    
    void load_waypoints() {
        std::ifstream file(CSV_PATH);
        if (!file.is_open()) {
            RCLCPP_ERROR(this->get_logger(), "❌ CSV 파일 열기 실패: %s", CSV_PATH.c_str());
            return;
        }
        std::string line;
        std::getline(file, line); 
        while (std::getline(file, line)) {
            std::stringstream ss(line);
            std::string cell;
            Waypoint wp;
            if (std::getline(ss, cell, ',')) wp.x = std::stod(cell);
            if (std::getline(ss, cell, ',')) wp.y = std::stod(cell);
            global_path_.push_back(wp);
        }
        RCLCPP_INFO(this->get_logger(), "✅ 웨이포인트 %lu개 로드 완료!", global_path_.size());
    }

    void scan_callback(const sensor_msgs::msg::LaserScan::SharedPtr msg) { (void)msg; }

    Waypoint get_lookahead_point(double lookahead_dist) {
        double min_dist = 10000.0;
        int closest_idx = -1;

        for (size_t i = 0; i < global_path_.size(); i++) {
            double dx = global_path_[i].x - current_x_;
            double dy = global_path_[i].y - current_y_;
            double dist = std::sqrt(dx*dx + dy*dy);
            if (dist < min_dist) {
                min_dist = dist;
                closest_idx = i;
            }
        }
        
        int target_idx = closest_idx;
        for (size_t i = 0; i < global_path_.size(); i++) {
            int curr_idx = (closest_idx + i) % global_path_.size();
            double dx = global_path_[curr_idx].x - current_x_;
            double dy = global_path_[curr_idx].y - current_y_;
            double dist = std::sqrt(dx*dx + dy*dy);

            if (dist > lookahead_dist) {
                target_idx = curr_idx;
                break;
            }
        }
        return global_path_[target_idx];
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

    void request_callback(const ride_service_interfaces::msg::RideRequest::SharedPtr msg) {
        if (state_ == State::IDLE || state_ == State::MISSION_COMPLETE) {
            RCLCPP_INFO(this->get_logger(), "🔔 호출 수신! 이동 시작.");
            pickup_loc_ = msg->pickup_location;
            dropoff_loc_ = msg->dropoff_location;
            state_ = State::GOING_TO_PICKUP;
        }
    }

    double get_distance_to(geometry_msgs::msg::Point target) {
        return std::sqrt(std::pow(current_x_ - target.x, 2) + std::pow(current_y_ - target.y, 2));
    }

    void control_loop() {
        ackermann_msgs::msg::AckermannDriveStamped drive_msg;
        drive_msg.header.stamp = this->get_clock()->now();
        drive_msg.header.frame_id = "base_link";
        double steering_angle = 0.0;
        double speed = 0.0;

        if (!global_path_.empty() && state_ != State::IDLE && state_ != State::AT_PICKUP && state_ != State::MISSION_COMPLETE) {
            double lookahead_dist = 0.6; 
            Waypoint target = get_lookahead_point(lookahead_dist);
            
            // [시각화] 빨간 점 발행
            publish_target_marker(target);

            double dx = target.x - current_x_;
            double dy = target.y - current_y_;
            
            double local_y = std::sin(-current_yaw_) * dx + std::cos(-current_yaw_) * dy;
            double curvature = 2.0 * local_y / (lookahead_dist * lookahead_dist);
            steering_angle = curvature;
            speed = 1.0;
        }

        switch (state_) {
            case State::IDLE: speed = 0.0; break;
            case State::GOING_TO_PICKUP:
                if (get_distance_to(pickup_loc_) < 2.5) {
                    state_ = State::AT_PICKUP;
                    one_shot_timer_ = this->create_wall_timer(3s, [this]() { state_ = State::GOING_TO_DROPOFF; one_shot_timer_->cancel(); });
                }
                break;
            case State::AT_PICKUP: speed = 0.0; break;
            case State::GOING_TO_DROPOFF:
                if (get_distance_to(dropoff_loc_) < 1.5) {
                    state_ = State::MISSION_COMPLETE;
                    one_shot_timer_ = this->create_wall_timer(2s, [this]() { state_ = State::IDLE; one_shot_timer_->cancel(); });
                }
                break;
            case State::MISSION_COMPLETE: speed = 0.0; break;
        }
        drive_msg.drive.steering_angle = std::max(-0.4, std::min(0.4, steering_angle));
        drive_msg.drive.speed = speed;
        drive_pub_->publish(drive_msg);
        
        publish_path_marker();
    }

    void publish_path_marker() {
        visualization_msgs::msg::Marker points;
        points.header.frame_id = "map";
        points.header.stamp = this->get_clock()->now();
        points.ns = "waypoints";
        points.action = visualization_msgs::msg::Marker::ADD;
        points.pose.orientation.w = 1.0;
        points.id = 0;
        points.type = visualization_msgs::msg::Marker::POINTS;
        points.scale.x = 0.1; points.scale.y = 0.1;
        points.color.g = 1.0f; points.color.a = 1.0;
        for (const auto& wp : global_path_) {
            geometry_msgs::msg::Point p; p.x = wp.x; p.y = wp.y;
            points.points.push_back(p);
        }
        marker_pub_->publish(points);
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
        marker.pose.orientation.w = 1.0;
        marker.scale.x = 0.5; marker.scale.y = 0.5; marker.scale.z = 0.5;
        marker.color.r = 1.0f; marker.color.a = 1.0; // 빨간색
        target_pub_->publish(marker);
    }

    rclcpp::Subscription<ride_service_interfaces::msg::RideRequest>::SharedPtr request_sub_;
    rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
    rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
    rclcpp::Publisher<ackermann_msgs::msg::AckermannDriveStamped>::SharedPtr drive_pub_;
    
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr marker_pub_;
    rclcpp::Publisher<visualization_msgs::msg::Marker>::SharedPtr target_pub_; 

    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::TimerBase::SharedPtr one_shot_timer_;
    State state_ = State::IDLE;
    geometry_msgs::msg::Point target_loc_, pickup_loc_, dropoff_loc_;
    // 중복 선언 제거됨 (이 자리에 변수 없음)
    double current_x_ = 0.0, current_y_ = 0.0, current_yaw_ = 0.0;
};

int main(int argc, char * argv[]) {
    std::setlocale(LC_NUMERIC, "C");
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<RideServiceManager>());
    rclcpp::shutdown();
    return 0;
}
