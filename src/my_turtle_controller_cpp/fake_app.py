import yaml

def new_request():
    print("\n=== 🚖 자율주행 택시 호출 앱 ===")
    user_id = input("사용자 ID (예: user_1): ")
    
    # 정류장 좌표 프리셋 (매니저 코드와 일치시킴)
    stations = {
        '1': {'x': 3.32, 'y': 10.3},
        '2': {'x': 22.8, 'y': 16.5},
        '3': {'x': 49.1, 'y': 9.11},
        '4': {'x': 37.4, 'y': 38.6},
        '5': {'x': 3.44, 'y': 33.7}
    }

    # [수정] 메뉴판도 새 이름으로 변경
    print("\n--- 정류장 목록 ---")
    print("1. 두 집 앞 (초기 위치)")
    print("2. 시장")
    print("3. 삼거리 맞은편")
    print("4. 가장 먼 곳")
    print("5. 고ㅋ")

    # [수정] 입력 범위가 1~3에서 1~5로 늘어남
    s_idx = input("출발 정류장 번호 (1-5): ")
    e_idx = input("도착 정류장 번호 (1-5): ")    
    if s_idx not in stations or e_idx not in stations:
        print("잘못된 번호입니다.")
        return

    start = stations[s_idx]
    end = stations[e_idx]

    # YAML 파일 읽기 (기존 데이터 유지)
    try:
        with open('requests.yaml', 'r') as f:
            data = yaml.safe_load(f) or {'requests': {}}
    except FileNotFoundError:
        data = {'requests': {}}

    # 데이터 업데이트
    data['requests'][user_id] = {
        'status': 'new',
        'pickup': {'x': start['x'], 'y': start['y']},
        'dropoff': {'x': end['x'], 'y': end['y']}
    }

    # YAML 파일 저장
    with open('requests.yaml', 'w') as f:
        yaml.dump(data, f)
    print(f"✅ {user_id}님의 호출이 전송되었습니다! (requests.yaml 업데이트됨)")

if __name__ == "__main__":
    while True:
        new_request()
