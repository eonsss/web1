"""고장 의심 판정 상태머신 (영상 처리와 분리, 관측값만 입력받음).

고장 의심 시나리오
  NO_DOOR_CLOSE : 사람이 탑승했는데 문이 닫히지 않은 채(문 움직임 없이) 다시 하차
  SHORT_RIDE    : 문이 닫혔다가 정상 이동시간보다 훨씬 빨리 열리고 하차
                  (밖이 보이는 호기는 창밖 움직임이 없으면 확정적 증거)
  STUCK_CLOSED  : 문 닫힘 + 탑승객 있음 + 장시간 이동 없음(갇힘 가능성)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from .config import ElevatorConfig


class Level(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Observation:
    ts: float                      # 초 단위 시각
    door_open: Optional[bool]      # None: 판별 불가(직전 상태 유지)
    people: int                    # 카 내부 인원
    scenery_motion: Optional[float] = None  # 창밖 움직임 세기(벽 호기는 None)


@dataclass
class FaultEvent:
    elevator_id: int
    ts: float
    kind: str
    level: Level
    detail: str


class ElevatorFaultDetector:
    # 창밖 움직임으로 인정하는 최소 세기 (vision.SceneryMotion 단위)
    MOTION_THRESHOLD = 1.5

    def __init__(self, cfg: ElevatorConfig, on_event: Callable[[FaultEvent], None]):
        self.cfg = cfg
        self.on_event = on_event
        self.door_open = True
        self.last_people = 0
        # 문 열림 구간 상태
        self.inside_since: Optional[float] = None
        self.boarded_flag = False
        # 문 닫힘 구간 상태
        self.closed_at: Optional[float] = None
        self.people_at_close = 0
        self.motion_seen = False
        self.stuck_reported = False
        # 재개방 직후 하차 감시
        self.pending: Optional[dict] = None
        self.history: deque[float] = deque()
        self.last_alert_ts = -1e18

    # ---------------------------------------------------------------- 입력
    def update(self, obs: Observation) -> None:
        door_open = self.door_open if obs.door_open is None else obs.door_open
        if door_open != self.door_open:
            if door_open:
                self._on_open(obs)
            else:
                self._on_close(obs)
            self.door_open = door_open

        if self.door_open:
            self._tick_open(obs)
        else:
            self._tick_closed(obs)
        self._tick_pending(obs)
        self.last_people = obs.people

    # ------------------------------------------------------------ 상태 전이
    def _on_close(self, obs: Observation) -> None:
        self.closed_at = obs.ts
        self.people_at_close = max(self.last_people, obs.people)
        self.motion_seen = False
        self.stuck_reported = False
        self.inside_since = None  # 문이 닫혔으므로 NO_DOOR_CLOSE 감시 종료

    def _on_open(self, obs: Observation) -> None:
        if self.closed_at is None or self.people_at_close == 0:
            self.closed_at = None
            return
        dur = obs.ts - self.closed_at
        moved = self.motion_seen if self.cfg.see_through else None
        short = dur < self.cfg.min_travel_sec
        # 밖이 보이는 호기: 창밖 움직임이 있었다면 정상 운행
        if short and moved is not True:
            self.pending = {
                "deadline": obs.ts + self.cfg.exit_window_sec,
                "dur": dur,
                "moved": moved,
                "people": self.people_at_close,
            }
        self.closed_at = None

    # ----------------------------------------------------------- 주기 처리
    def _tick_open(self, obs: Observation) -> None:
        if obs.people > 0:
            if self.inside_since is None:
                self.inside_since = obs.ts
        elif self.inside_since is not None:
            stay = obs.ts - self.inside_since
            self.inside_since = None
            # 탑승했다가 문 닫힘 없이 다시 하차 → 문 움직임 없는 의심
            if self.pending is None and stay >= self.cfg.door_close_timeout_sec:
                self._raise(
                    obs.ts, "NO_DOOR_CLOSE", Level.WARNING,
                    f"탑승 후 {stay:.0f}초간 문이 닫히지 않고 하차",
                )

    def _tick_closed(self, obs: Observation) -> None:
        if self.closed_at is None:
            return
        if obs.scenery_motion is not None and obs.scenery_motion >= self.MOTION_THRESHOLD:
            self.motion_seen = True
        if self.stuck_reported or self.people_at_close == 0:
            return
        dur = obs.ts - self.closed_at
        if self.cfg.see_through:
            if not self.motion_seen and dur >= self.cfg.no_motion_stuck_sec:
                self.stuck_reported = True
                self._raise(obs.ts, "STUCK_CLOSED", Level.CRITICAL,
                            f"문 닫힘 {dur:.0f}초째 창밖 움직임 없음 (승객 {self.people_at_close}명)")
        elif dur >= self.cfg.max_closed_sec:
            self.stuck_reported = True
            self._raise(obs.ts, "STUCK_CLOSED", Level.CRITICAL,
                        f"문 닫힘 {dur:.0f}초 경과 (승객 {self.people_at_close}명)")

    def _tick_pending(self, obs: Observation) -> None:
        p = self.pending
        if p is None:
            return
        if obs.people < p["people"]:  # 누군가 내림
            self.pending = None
            strong = p["moved"] is False
            how = "창밖 움직임 없음" if strong else "벽 호기: 이동 여부 확인 불가"
            self._raise(
                obs.ts, "SHORT_RIDE", Level.CRITICAL if strong else Level.WARNING,
                f"문 닫힘 {p['dur']:.0f}초(정상 최소 {self.cfg.min_travel_sec:.0f}초) 후 열림, 하차 ({how})",
            )
        elif obs.ts > p["deadline"]:
            self.pending = None  # 하차 없음 → 단순 문 재개방

    # ------------------------------------------------------------- 알림
    def _raise(self, ts: float, kind: str, level: Level, detail: str) -> None:
        self.history.append(ts)
        while self.history and ts - self.history[0] > self.cfg.escalate_window_sec:
            self.history.popleft()
        if level is Level.WARNING and len(self.history) >= self.cfg.escalate_count:
            level = Level.CRITICAL
            detail += f" [최근 {len(self.history)}회 반복]"
        if ts - self.last_alert_ts < self.cfg.cooldown_sec and level is Level.WARNING:
            return
        self.last_alert_ts = ts
        self.on_event(FaultEvent(self.cfg.id, ts, kind, level, detail))
