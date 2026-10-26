# 에스컬레이터 고장 감시 (프로토타입 1단계)

영상 분석 계층이 넘겨주는 `운행 여부`, `탑승 인원`, `진입/하차 이벤트`로 고장을 판정하는 상태 머신.

- `logic.py` : 판정 로직 (영상/네트워크 비의존)
- `tests/test_logic.py` : 시나리오 시뮬레이션 테스트 (`python -m unittest discover -s tests`)

## 판정 규칙
| 상황 | 경보 |
|---|---|
| 탑승 중 정지 | RIDE_STOPPED (critical) |
| 탑승자 있는데 start_grace_s 내 기동 안 함 (정/역방향 공통) | FAIL_TO_START (critical) |
| 마지막 정방향 하차 후 n-허용오차 이전에 정지 | EARLY_STOP (major) |
| 마지막 정방향 하차 후 n+허용오차가 지나도 운행 | STUCK_RUNNING (warning) |
| 상시 가동형이 정지 | STOPPED_ALWAYS_ON (major) |

역방향으로 비워진 경우에는 정지 타이머를 시작하지 않는다(기대 상태 없음).
`maintenance=True`면 모든 판정을 억제한다.

## 다음 단계
1. 영상 소스 확인 (RTSP 주소 / NVR 모델) 후 입력 계층 작성
2. 대수별로 n(stop_delay_s), start_grace_s 현장 측정
3. 핸드레일 ROI 움직임 감지 -> `running`
4. 사람 검출+트래킹, 가상 라인 -> `riders`, 진입/하차 이벤트
5. 알림 UI, 22대 동시 처리, 섀도 모드(로그만)
