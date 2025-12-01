# 농촌 자율주행 차량 호출 시스템 – Web 프론트 (callbus)

ROS2 기반 **농촌 자율주행 셔틀 호출 서비스**를 위한 웹 프론트/예약 서버입니다.  
고령자도 쉽게 사용할 수 있도록 **큰 글씨, 단순한 단계 진행, 직관적인 버튼**을 목표로 디자인했습니다.

이 레포지토리는

- 브라우저에서 예약 정보를 입력하고
- 서버(FastAPI)가 이를 받아 YAML 파일에 저장/조회하며
- 추후 **ROS2 시뮬레이션/실차 제어 노드와 연동**될 것을 전제로 한 구조

까지를 담당합니다.

---

## 1. 기술 스택

- **Backend**
  - Python 3.x
  - [FastAPI](https://fastapi.tiangolo.com/)
  - [Uvicorn](https://www.uvicorn.org/)
  - `PyYAML` – 간단한 데이터 저장용 (`userinfo.yml`, `reservation.yml`)

- **Frontend**
  - 순수 HTML / CSS / Vanilla JavaScript
  - 한국어 UI, 고령자 친화 레이아웃

---

## 2. 주요 기능

### 2-1. 호출 예약 플로우

1. **예약자 정보 입력 (`/호출예약`, `reservation_1.html`)**
   - 예약자 이름
   - 전화번호
   - 예약자 식별번호(user_id)
   - 비상 연락망
   - 탑승 인원
   - 탑승 지원 필요 여부(checkbox)
   - `userinfo.yml`에 등록된 user_id & 정보와 **본인 인증** 후 다음 단계로 이동

2. **위치 및 날짜/시간 설정 (`/호출위치선택`, `reservation_2.html`)**
   - 지도 영역(추후 실제 지도 연동 예정)
   - **날짜 선택 (오늘 ~ 1개월 이내)**
   - 날짜가 오늘이면:
     - `5분 뒤`, `10분 뒤`, `30분 뒤`, `1시간 뒤` 버튼
     - 현재 시각 기준으로 N분 뒤의 도착 시각을 계산해서 서버로 전송
   - 오늘이 아니면:
     - `time` input에서 직접 도착 시각 선택
   - 선택 결과는 서버로 `date`, `arrival_time`(예: `"2025-11-26"`, `"17:59"`) 형식으로 전송
   - `reservation.yml`에 user_id 기준으로 저장

3. **예약 확인 (`/예약확인`, `check_number.html`)**
   - 사용자가 **예약자 식별번호(= user_id 또는 예약 코드)** 입력
   - 서버에서 `reservation.yml`을 읽고 해당 코드가 있는지 확인
   - 있으면 `/예약정보확인?code=...` 으로 이동

4. **예약 상세 조회 (`/예약정보확인`, `check_reservation.html`)**
   - URL 쿼리스트링의 `code` 값을 읽어옴
   - `fetch('/api/reservation?code=...')`로 서버에 예약 정보 요청
   - 서버는 `reservation.yml`에서 해당 key를 찾아 JSON으로 반환
   - 화면에 예약자 이름, 전화번호, 비상 연락망, 인원 등 표시  
     (assist, 출발/도착지, 예상 소요시간 등은 추후 확장)

---

## 3. 데이터 저장 구조

현재는 DB 대신 **YAML 파일**로 간단히 저장합니다.

- `userinfo.yml`
  - 미리 등록된 사용자 계정/프로필
  - 예시:

    ```yaml
    sample-user-1234:
      name: 홍길동
      phone: "01012345678"
      emergency: "01099998888"
      passengers: 2
      assist: true
    ```

- `reservation.yml`
  - 실제 예약 건(날짜 + 도착 시간 등)을 user_id 기준으로 저장
  - 예시:

    ```yaml
    sample-user-1234:
      date: "2025-11-26"
      time: "17:59"
    ```

---

## 4. 프로젝트 구조(요약)
> 실제 파일명/경로는 레포지토리를 기준으로 약간 다를 수 있습니다.

```text
callbus/
├─ app/
│  └─ __init__.py           # (필요 시 FastAPI 앱 팩토리로 확장 예정)
├─ statics/
│  ├─ index.html            # 메인 화면
│  ├─ reservation_1.html    # 호출 예약 1단계 – 예약자 정보 입력
│  ├─ reservation_2.html    # 호출 예약 2단계 – 위치 + 날짜/시간
│  ├─ reservation_3.html    # (필요 시) 경로/소요시간 확인 페이지
│  ├─ check_number.html     # 예약 코드 입력 화면 (/예약확인)
│  └─ check_reservation.html# 예약 상세 조회 화면 (/예약정보확인)
├─ main.py                  # FastAPI 엔트리포인트
├─ userinfo.yml             # 사전 등록 사용자 정보
├─ reservation.yml          # 실제 예약 데이터
├─ requirments.txt          # 의존성 목록 (fastapi, uvicorn, pyyaml 등)
└─ README.md                # (이 파일)
```

## 5. 실행 방법

1) 레포지토리 클론
git clone https://github.com/ping1239/callbus.git
cd callbus

2) 가상 환경(선택)
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

3) 패키지 설치
pip install -r requirments.txt
# 혹은 필요 시
pip install fastapi uvicorn pyyaml

4) 실행
uvicorn main:app --reload
http주소로 접속

