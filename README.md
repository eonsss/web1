# 엘리베이터 고장 감지 (CCTV 기반)

방재실 고장신호가 누락될 때를 대비해, 카 내부 CCTV로 "탑승 → 이동 없이 하차" 패턴을 감지해 알립니다.

## 판정 규칙 (`elevator_monitor/core.py`)
| 종류 | 조건 | 등급 |
|---|---|---|
| `NO_DOOR_CLOSE` | 사람이 탔는데 `door_close_timeout_sec`(12초) 동안 문이 안 닫히고 하차 | WARNING |
| `SHORT_RIDE` | 문 닫힘→열림이 `min_travel_sec`(실측 1개 층 이동시간 `one_floor_sec`의 70%: 1~5호기 12.6초, 6~12호기 7초, 13호기 8.4초)보다 짧고, 열린 뒤 `exit_window_sec`(10초) 안에 하차 | 벽 호기(1~5): WARNING / 창 호기(6~13): 창밖 움직임 없으면 CRITICAL |
| `STUCK_CLOSED` | 문 닫힘 + 승객 있음 + 이동 없음 지속 (창 호기 20초, 벽 호기 층수 기반 상한) | CRITICAL |

- WARNING이 15분 안에 2회 이상 반복되면 CRITICAL로 승격, 같은 호기 WARNING은 5분 쿨다운.
- 1~5호기(벽)는 이동 여부를 직접 볼 수 없어 **문 닫힘 시간**만으로 판단 → 오탐 가능성이 높아 WARNING 시작.
- 6~13호기는 창밖 광학흐름으로 실제 이동을 확인해 정상 운행 오탐을 제거.
- 빈 카의 문 개폐, 문만 다시 열리고 아무도 안 내리는 경우는 무시.

## 구성
- `config/elevators.json` – 13대 설정. 1,4,5호기=1~5층, 9,11호기=1~3층, 2,3,6,8,10,12,13호기=1~2층 반영. **7호기만 층 범위 미확정(`[1,1]` 임시값)**.
- `vision.py` – 문 개폐(기준 이미지 비교), 창밖 움직임(광학흐름), 인원수(YOLO, 없으면 근사치)
- `alerts.py` – 로그(`faults.jsonl`) + 웹훅(선택)
- `tests/` – 시나리오 시뮬레이션 테스트 (`pytest`)

## 실행
```
pip install -r requirements.txt
mkdir refs   # 호기별 '빈 카·문 닫힘' 기준 사진을 ev01.jpg ... ev13.jpg 로 저장
python -m elevator_monitor.main --config config/elevators.json --webhook <URL> --only 6 7
```

## 현장 적용 전 필수 보정
실제 영상 없이 만든 초기 버전이라 아래 값은 **현장 영상으로 조정**해야 합니다.
1. `door_roi`, `window_roi` (카메라 화각별 문/유리창 위치) 및 문 임계값(`DoorStateEstimator.hi/lo`)
2. `one_floor_sec` – 호기별 실측값(현재 1~5호기 18초, 6~12호기 10초, 13호기 12초)이 들어 있음. 인식 지연이 크면 `min_travel_sec`을 직접 지정
3. `MOTION_THRESHOLD` / 광학흐름 보정상수, 인원수 근사치(YOLO 설치 권장)
4. 먼저 알림 없이 로그만으로 1~2주 돌려 오탐률을 보고 임계값을 정하세요.

한계: 카메라 앵글상 문이 안 보이거나 야간 조명 변화가 크면 문 상태 판별이 흔들릴 수 있습니다. 이 도구는 방재실 신호를 **보완**하는 용도입니다.
