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
from nav_msgs.msg import Path

# ================= 설정 =================
MAP_PATH = "/home/misys/ros2_ws/src/f1tenth_gym_ros/maps/rural_map.png"
RESOLUTION = 0.08
ORIGIN_X = 0.0
ORIGIN_Y = 0.0
# ========================================

class GlobalPlanner(Node):
    def __init__(self):
        super().__init__('global_planner')
        
        self.get_logger().info("🗺️ 지도를 읽고 그래프를 생성 중... (잠시 대기)")
        self.graph, self.pixel_points = self.create_graph_from_map()
        self.tree = cKDTree(self.pixel_points)
        self.get_logger().info("✅ 그래프 생성 완료! 호출 대기 중...")

        self.create_subscription(RideRequest, '/ride_request', self.handle_request, 10)
        self.path_pub = self.create_publisher(Path, '/planned_path', 10)

    def create_graph_from_map(self):
        img = cv2.imread(MAP_PATH, cv2.IMREAD_GRAYSCALE)
        if img is None:
            self.get_logger().error(f"이미지를 찾을 수 없습니다: {MAP_PATH}")
            return None, None

        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)
        
        skeleton = skeletonize(binary // 255)
        y_idx, x_idx = np.where(skeleton == 1)
        points = np.column_stack((x_idx, y_idx))

        G = nx.Graph()
        for p in points:
            G.add_node(tuple(p))

        for p in points:
            x, y = p
            neighbors = [
                (x+1, y), (x-1, y), (x, y+1), (x, y-1),
                (x+1, y+1), (x-1, y-1), (x+1, y-1), (x-1, y+1)
            ]
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

    def handle_request(self, msg):
        start_wp = msg.pickup_location
        end_wp = msg.dropoff_location
        
        self.get_logger().info(f"🔍 경로 계산 요청: ({start_wp.x:.1f}, {start_wp.y:.1f}) -> ({end_wp.x:.1f}, {end_wp.y:.1f})")

        start_node = self.get_closest_node(start_wp.x, start_wp.y)
        end_node = self.get_closest_node(end_wp.x, end_wp.y)

        try:
            path_pixels = nx.astar_path(self.graph, start_node, end_node, weight='weight')
            
            ros_path = Path()
            ros_path.header.frame_id = "map"
            
            for px, py in path_pixels:
                pose = PoseStamped()
                wx, wy = self.pixel_to_world(px, py)
                pose.pose.position.x = wx
                pose.pose.position.y = wy
                ros_path.poses.append(pose)

            self.path_pub.publish(ros_path)
            self.get_logger().info(f"✅ 경로 생성 완료! (길이: {len(path_pixels)} points)")

        except nx.NetworkXNoPath:
            self.get_logger().error("❌ 경로를 찾을 수 없습니다! (길이 끊겨 있음)")
        except Exception as e:
            self.get_logger().error(f"❌ 오류 발생: {e}")

def main(args=None):
    # [수정] rclcpp -> rclpy 로 변경
    rclpy.init(args=args)
    node = GlobalPlanner()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
