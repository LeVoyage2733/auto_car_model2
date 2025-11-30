#!/bin/bash
echo "🔧 [자동 설정] 자율주행 환경 설정을 시작합니다..."

# 1. 기존 라이브러리 충돌 해결 (삭제)
echo "1️⃣ 꼬인 라이브러리 제거 중..."
pip uninstall -y f110-gym numpy numba gym pyglet

# 2. '황금 조합' 버전 설치 (Numpy 1.21.6 등)
echo "2️⃣ 호환성 버전(Golden Set) 설치 중..."
pip install "pip<24.0"
pip install "numpy==1.21.6" "gym==0.19.0" "numba==0.56.4" "pyglet<1.5"

# 3. 시뮬레이터 연결
echo "3️⃣ F1Tenth 시뮬레이터 연결 중..."
# 라이브러리 위치 체크 및 설치
if [ -d "/home/misys/ros2_ws/f1tenth_gym" ]; then
    cd /home/misys/ros2_ws/f1tenth_gym
    pip install -e .
elif [ -d "/home/misys/f1tenth_gym" ]; then
    cd /home/misys/f1tenth_gym
    pip install -e .
else
    echo "⚠️ 경고: f1tenth_gym 폴더를 찾을 수 없습니다. 사용자가 직접 연결해주세요."
fi

echo "🎉 [설정 완료] 이제 ros2 launch 명령어로 실행하세요!"
# 맨 마지막에 추가
echo ""
echo "============================================"
echo "✅ 모든 설정이 끝났습니다!"
echo "이제 아래 순서대로 실행하세요:"
echo "1. ros2 launch f1tenth_gym_ros gym_bridge_launch.py"
echo "2. (새 터미널) ros2 run my_turtle_controller_cpp ride_service_manager"
echo "3. (새 터미널) python3 src/my_turtle_controller_cpp/src/global_planner.py"
echo "4. (새 터미널) cd callbus && uvicorn main:app --host 0.0.0.0 --port 8000"
echo "============================================"
