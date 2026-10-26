"""엘리베이터별 설정 로드."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ElevatorConfig:
    id: int
    floors: list[int]                 # 운행 층 [최저, 최고]
    see_through: bool                 # True: 6~13호기(밖이 보임), False: 1~5호기(벽)
    camera: str = ""                  # RTSP URL 또는 영상 파일 경로
    # --- 판정 임계값(초). 현장 영상으로 calibrate 후 조정 ---
    min_travel_sec: float = 8.0       # 문 닫힘→열림 최소 정상 이동시간(1개 층 이동 기준)
    door_close_timeout_sec: float = 12.0   # 탑승 후 문이 닫히지 않고 하차까지 허용하는 시간
    exit_window_sec: float = 10.0     # 문이 다시 열린 뒤 이 시간 안의 하차를 '내리는 동작'으로 봄
    min_inside_sec: float = 2.0       # 사람 인식 깜빡임 제거용 최소 탑승 시간
    no_motion_stuck_sec: float = 20.0 # (밖이 보이는 호기) 문 닫힘 + 사람 + 움직임 없음 지속시간
    escalate_count: int = 2           # 이 횟수 이상 의심이 반복되면 CRITICAL
    escalate_window_sec: float = 900.0
    cooldown_sec: float = 300.0       # 같은 호기 중복 알림 억제
    # --- 영상 ROI (x, y, w, h 비율 0~1) ---
    door_roi: list[float] = field(default_factory=lambda: [0.3, 0.0, 0.4, 1.0])
    window_roi: list[float] | None = None   # 밖이 보이는 유리창 영역(6~13호기)

    @property
    def span(self) -> int:
        return self.floors[1] - self.floors[0] + 1

    @property
    def max_closed_sec(self) -> float:
        """(벽 호기) 이보다 오래 문이 닫혀 있으면 갇힘 가능성으로 알림."""
        return 3 * (25.0 + 6.0 * (self.span - 1))


def load_config(path: str | Path) -> dict[int, ElevatorConfig]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    out: dict[int, ElevatorConfig] = {}
    for item in raw["elevators"]:
        merged = {**defaults, **item}
        cfg = ElevatorConfig(**merged)
        out[cfg.id] = cfg
    return out
