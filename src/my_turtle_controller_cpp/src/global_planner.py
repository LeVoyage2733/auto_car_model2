#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import cv2
import numpy as np
from skimage.morphology import skeletonize
import networkx as nx
from scipy.spatial import cKDTree
from geometry_msgs.msg import Point, PoseStamped
from ride_service_interfaces.msg import RideRequest
from nav_msgs.msg import Path, Odometry
# deque 대신 일반 리스트 사용 (순서 섞기 위해)

# ================= 설정 =================
MAP_PATH = "/home/misys/ros2_ws/src/f1tenth_gym_ros/maps/rural_map.png"
RESOLUTION = 0.08
ORIGIN_X = 0.0
ORIGIN_Y = 0.0
# ========================================

class GlobalPlanner(Node):
    def __init__(self):
        super().__init__('global_planner')
        
        self.get_logger().info("🗺️ [스마트 관제탑] 지도 로딩 중...")
        self.graph, self.pixel_points = self.create_graph_from_map()
        self.tree = cKDTree(self.pixel_points)
        self.get_logger().info("✅ 준비 완료! 최적 배차 대기 중...")

        self.create_subscription(RideRequest, '/ride_request', self.handle_request, 10)
        self.create_subscription(Odometry, '/ego_racecar/odom', self.odom_callback, 10)
        self.path_pub = self.create_publisher(Path, '/planned_path', 10)

        self.request_queue = [] # 리스트로 변경
        self.is_busy = False         
        self.current_goal = None     
        self.car_pose = (3.32, 10.3) 

        self.create_timer(1.0, self.check_mission_status)

    def create_graph_from_map(self):
        img = cv2.imread(MAP_PATH, cv2.IMREAD_GRAYSCALE)
        if img is None: return None, None
        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
        skeleton = skeletonize(binary // 255)
        y_idx, x_idx = np.where(skeleton == 1)
        points = np.column_stack((x_idx, y_idx))
        G = nx.Graph()
        for p in points: G.add_node(tuple(p))
        for p in points:
            x, y = p
            neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1), (x+1, y+1), (x-1, y-1), (x+1, y-1), (x-1, y+1)]
            for n in neighbors:
                if G.has_node(n):
                    dist = 1.414 if x != n[0] and y != n[1] else 1.0
                    G.add_edge(tuple(p), n, weight=dist)
        return G, points

    def world_to_pixel(self, wx, wy):
        height_px = 811 
        px = int((wx - ORIGIN_X) / RESOLUTION)
        py = int(height_px - ((wy - ORIGIN_Y) / RESOLUTION))
        return (px, py)

    def pixel_to_world(self, px, py):
        height_px = 811
        wx = px * RESOLUTION + ORIGIN_X
        wy = (height_px - py) * RESOLUTION + ORIGIN_Y
        return wx, wy

    def get_closest_node(self, wx, wy):
        target_px = self.world_to_pixel(wx, wy)
        _, idx = self.tree.query(target_px)
        return tuple(self.pixel_points[idx])

    def odom_callback(self, msg):
        self.car_pose = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def handle_request(self, msg):
        self.request_queue.append(msg)
        self.get_logger().info(f"📝 호출 접수! (대기: {len(self.request_queue)}명)")

    def check_mission_status(self):
        # 1. 운행 종료 확인
        if self.is_busy and self.current_goal:
            dist = np.sqrt((self.car_pose[0] - self.current_goal.x)**2 + (self.car_pose[1] - self.current_goal.y)**2)
            if dist < 2.0: 
                self.get_logger().info("🏁 하차 완료! 다음 최적 손님을 찾습니다.")
                self.is_busy = False
                self.current_goal = None

        # 2. [핵심] 가장 가까운 손님 찾기 (Greedy Search)
        if not self.is_busy and self.request_queue:
            best_idx = -1
            min_dist = 99999.9
            
            # 대기열을 전부 뒤져서 내 차랑 제일 가까운 픽업지를 찾음
            for i, req in enumerate(self.request_queue):
                # 차 위치 -> 픽업지 거리 계산
                d = np.sqrt((self.car_pose[0] - req.pickup_location.x)**2 + (self.car_pose[1] - req.pickup_location.y)**2)
                if d < min_dist:
                    min_dist = d
                    best_idx = i
            
            if best_idx != -1:
                # 가장 가까운 손님을 목록에서 꺼냄
                next_mission = self.request_queue.pop(best_idx)
                self.get_logger().info(f"💡 최적 경로 발견! 거리: {min_dist:.1f}m")
                self.process_mission(next_mission)

    def process_mission(self, msg):
        self.is_busy = True
        self.current_goal = msg.dropoff_location
        
        start_wp = msg.pickup_location
        end_wp = msg.dropoff_location
        
        self.get_logger().info(f"🚀 주행 시작: ({start_wp.x:.1f},{start_wp.y:.1f}) -> ({end_wp.x:.1f},{end_wp.y:.1f})")

        # (A) 차 -> 픽업지 경로
        start_node_1 = self.get_closest_node(self.car_pose[0], self.car_pose[1])
        end_node_1 = self.get_closest_node(start_wp.x, start_wp.y)
        
        # (B) 픽업지 -> 도착지 경로
        start_node_2 = end_node_1
        end_node_2 = self.get_closest_node(end_wp.x, end_wp.y)

        try:
            # 두 경로를 이어 붙임 (Path Stitching)
            path_1 = nx.astar_path(self.graph, start_node_1, end_node_1, weight='weight')
            path_2 = nx.astar_path(self.graph, start_node_2, end_node_2, weight='weight')
            
            full_path = path_1 + path_2[1:] # 중복되는 연결점 제거 후 병합

            ros_path = Path()
            ros_path.header.frame_id = "map"
            
            for px, py in full_path:
                pose = PoseStamped()
                wx, wy = self.pixel_to_world(px, py)
                pose.pose.position.x = wx
                pose.pose.position.y = wy
                ros_path.poses.append(pose)

            self.path_pub.publish(ros_path)

        except Exception as e:
            self.get_logger().error(f"❌ 경로 계산 실패: {e}")
            self.is_busy = False 

def main(args=None):
    rclpy.init(args=args)
    node = GlobalPlanner()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
