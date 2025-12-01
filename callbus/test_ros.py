import asyncio
import websockets
import os

# WSL에서 윈도우(Host)의 IP를 자동으로 찾는 함수
def get_host_ip():
    try:
        # /etc/resolv.conf 파일에서 nameserver IP를 가져옴 (WSL 2 방식)
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if "nameserver" in line:
                    return line.split()[1]
    except:
        pass
    return "host.docker.internal" # 도커 환경일 경우 대비

async def listen_to_server():
    host_ip = get_host_ip()
    # 만약 위 코드로 IP를 못 찾으면 본인의 윈도우 IP를 직접 넣으셔도 됩니다.
    print(f"🔎 윈도우(서버) IP 탐색 중... 찾은 주소: {host_ip}")

    uri = f"ws://{host_ip}:8000/ws/vehicle/Bus01"
    
    print(f"🤖 [WSL 가상 ROS] 서버({uri})에 연결 시도 중...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ 연결 성공! 데이터 대기 중...")
            while True:
                message = await websocket.recv()
                print(f"\n⚡ [수신 성공] 서버 -> ROS: {message}")
                print("-" * 30)
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        print("팁: 윈도우 터미널에서 'uvicorn ... --host 0.0.0.0'으로 실행했는지 확인하세요.")

if __name__ == "__main__":
    asyncio.run(listen_to_server())
