import cv2
import numpy as np
from skimage.morphology import skeletonize
import pandas as pd
from scipy.spatial import cKDTree

# ==========================================
# 설정 (sim.yaml과 똑같이 맞춰주세요!)
# ==========================================
MAP_PATH = "/home/misys/ros2_ws/src/f1tenth_gym_ros/maps/rural_map.png"
RESOLUTION = 0.08  # 해상도
ORIGIN_X = 0.0
ORIGIN_Y = 0.0

# 차량 시작 위치 (1번 정류장) - 여기서부터 길 찾기를 시작함
START_X = 3.32
START_Y = 10.3
# ==========================================

def extract_smart_waypoints():
    print("🧹 스마트 웨이포인트 추출 시작...")
    
    # 1. 이미지 읽기
    img = cv2.imread(MAP_PATH, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("❌ 이미지를 못 찾겠어요! 경로를 확인하세요.")
        return

    # 2. 이진화 (검은선=0, 나머지=255)
    # 노이즈 제거를 위해 200 이상만 흰색으로 인정
    _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY)

    # [중요] 맵 테두리에 검은 선 두르기 (길이 맵 밖으로 새나가는 것 방지)
    h, w = binary.shape[:2]
    cv2.rectangle(binary, (0, 0), (w-1, h-1), 0, thickness=2)

    # 3. 시작 지점 픽셀 좌표 계산 (Meter -> Pixel)
    # ROS 좌표계(좌하단 0,0) -> 이미지 좌표계(좌상단 0,0) 변환
    start_px_x = int((START_X - ORIGIN_X) / RESOLUTION)
    start_px_y = int(h - ((START_Y - ORIGIN_Y) / RESOLUTION))

    print(f"📍 시작점 픽셀 좌표: ({start_px_x}, {start_px_y})")

    # 4. 스마트 도로 추출 (Flood Fill)
    # 시작점에서 '회색(128)' 물감을 붓습니다.
    # 검은 선에 막혀서 도로 밖(논밭)으로는 물감이 안 나갑니다.
    mask = np.zeros((h+2, w+2), np.uint8)
    flood_filled = binary.copy()
    cv2.floodFill(flood_filled, mask, (start_px_x, start_px_y), 128)

    # 5. 도로만 남기기
    # 회색(128)으로 변한 부분만 진짜 도로입니다. 나머지는 다 검은색(0)으로 지웁니다.
    road_only = np.zeros_like(binary)
    road_only[flood_filled == 128] = 255 # 진짜 도로만 흰색으로

    # (디버깅용) 추출된 도로 이미지 저장
    cv2.imwrite("debug_road_only.png", road_only)

    # 6. 뼈대 추출 (Skeletonize)
    skeleton = skeletonize(road_only // 255)
    y_idx, x_idx = np.where(skeleton == 1)

    if len(x_idx) == 0:
        print("❌ 도로 추출 실패! 시작 좌표가 벽(검은색) 위에 있거나 맵이 막혀있습니다.")
        return

    # 7. 픽셀 -> 미터 변환
    real_x = x_idx * RESOLUTION + ORIGIN_X
    real_y = (h - y_idx) * RESOLUTION + ORIGIN_Y

    points = np.column_stack((real_x, real_y))
    print(f"🔍 추출된 웨이포인트 개수: {len(points)}개")

    # 8. 정렬 (Nearest Neighbor)
    sorted_points = []
    start_node = np.array([START_X, START_Y])
    tree = cKDTree(points)
    _, idx = tree.query(start_node)
    
    current_idx = idx
    visited = set([current_idx])
    sorted_points.append(points[current_idx])

    while len(visited) < len(points):
        dists, idxs = tree.query(points[current_idx], k=10)
        found_next = False
        for next_idx in idxs:
            if next_idx not in visited:
                # 점프 거리 제한 (너무 멀리 튀지 않게)
                if np.linalg.norm(points[next_idx] - points[current_idx]) < 1.0:
                    visited.add(next_idx)
                    sorted_points.append(points[next_idx])
                    current_idx = next_idx
                    found_next = True
                    break
        if not found_next:
            for i in range(len(points)):
                if i not in visited:
                    current_idx = i
                    visited.add(i)
                    sorted_points.append(points[i])
                    break

    # 9. 저장
    df = pd.DataFrame(sorted_points, columns=['x', 'y'])
    df.to_csv('/home/misys/ros2_ws/src/my_turtle_controller_cpp/waypoints.csv', index=False)
    print("✅ 깔끔해진 웨이포인트 저장 완료!")

if __name__ == "__main__":
    extract_smart_waypoints()
