"""에스컬레이터 고장 판정 상태 머신.

영상 분석 계층이 넘겨주는 두 가지 관측값(운행 여부, 탑승 인원)과 진입/하차 이벤트만으로
"기대 상태"와 "실제 상태"를 비교한다. 영상/네트워크에 의존하지 않아 시뮬레이션으로 검증할 수 있다.
"""
from dataclasses import dataclass, field
from enum import Enum

ENTER_FWD, ENTER_REV, EXIT_FWD, EXIT_REV = "enter_fwd", "enter_rev", "exit_fwd", "exit_rev"


class Mode(str, Enum):
    ALWAYS_ON = "always_on"  # 상시 가동형
    STANDBY = "standby"      # 절전형 (사람 없으면 정지)


class Code(str, Enum):
    RIDE_STOPPED = "ride_stopped"      # 탑승 중 정지 (최우선)
    FAIL_TO_START = "fail_to_start"    # 탑승자가 있는데 기동 안 함 (정방향/역방향 진입 공통)
    EARLY_STOP = "early_stop"          # 마지막 하차 후 n초보다 일찍 정지
    STUCK_RUNNING = "stuck_running"    # n초가 지나도 정지하지 않음 (경고)
    STOPPED_ALWAYS_ON = "stopped_always_on"  # 상시 가동형이 정지


SEVERITY = {
    Code.RIDE_STOPPED: "critical",
    Code.FAIL_TO_START: "critical",
    Code.EARLY_STOP: "major",
    Code.STOPPED_ALWAYS_ON: "major",
    Code.STUCK_RUNNING: "warning",
}


@dataclass
class Config:
    mode: Mode = Mode.STANDBY
    stop_delay_s: float = 30.0       # n: 마지막 정방향 하차 후 정지까지 걸리는 시간 (현장 측정 필요)
    stop_tolerance_s: float = 5.0    # n ± 허용 오차
    start_grace_s: float = 5.0       # 탑승 감지 후 기동까지 허용 시간 (절전형 기동 지연)
    confirm_s: float = 2.0           # 조건이 이 시간 이상 지속돼야 경보 (오탐 방지)


@dataclass
class Alarm:
    t: float
    escalator: str
    code: Code
    severity: str
    raised: bool  # False면 해제

    def __str__(self):
        return f"[{self.t:7.1f}s] {self.escalator} {self.code.value} ({self.severity}) {'발생' if self.raised else '해제'}"


@dataclass
class Monitor:
    name: str
    cfg: Config = field(default_factory=Config)
    maintenance: bool = False  # True면 모든 판정 억제 (점검/운행 종료 시간)

    def __post_init__(self):
        self._riders = 0
        self._session_start = None   # riders 0 -> >0 시각
        self._ran_in_session = False
        self._exit_t = None          # 마지막 정방향 하차 시각 (타이머 무장 중일 때만 값 있음)
        self._cond_since = {}        # Code -> 조건이 처음 참이 된 시각
        self._active = set()

    def update(self, now, running, riders, events=()):
        """한 틱 처리. running: 운행 중인가, riders: 현재 탑승 인원, events: 이번 틱의 진입/하차 이벤트."""
        prev = self._riders
        self._riders = riders
        if riders > 0 and prev == 0:
            self._session_start, self._ran_in_session = now, False
        if riders > 0:
            self._exit_t = None            # 누군가 타고 있으면 정지 타이머 해제
            self._ran_in_session |= running
        elif prev > 0:                     # 마지막 승객이 방금 빠짐
            # 정방향 하차로 비워졌을 때만 정지 타이머 시작. 역방향은 기대 상태를 두지 않는다.
            self._exit_t = now if EXIT_FWD in events else None
            self._session_start = None

        true_now = set() if self.maintenance else self._violations(now, running)
        return self._debounce(now, true_now)

    def _violations(self, now, running):
        c, v = self.cfg, set()
        if running:
            if c.mode is Mode.STANDBY and self._riders == 0 and self._exit_t is not None \
                    and now - self._exit_t > c.stop_delay_s + c.stop_tolerance_s:
                v.add(Code.STUCK_RUNNING)
            return v
        if self._riders > 0:
            if self._ran_in_session:
                v.add(Code.RIDE_STOPPED)
            elif now - self._session_start > c.start_grace_s:
                v.add(Code.FAIL_TO_START)
        elif c.mode is Mode.ALWAYS_ON:
            v.add(Code.STOPPED_ALWAYS_ON)
        elif self._exit_t is not None and now - self._exit_t < c.stop_delay_s - c.stop_tolerance_s:
            v.add(Code.EARLY_STOP)
        return v

    def _debounce(self, now, true_now):
        out = []
        for code in Code:
            if code in true_now:
                since = self._cond_since.setdefault(code, now)
                if code not in self._active and now - since >= self.cfg.confirm_s:
                    self._active.add(code)
                    out.append(Alarm(now, self.name, code, SEVERITY[code], True))
            else:
                self._cond_since.pop(code, None)
                if code in self._active:
                    self._active.discard(code)
                    out.append(Alarm(now, self.name, code, SEVERITY[code], False))
        return out

    @property
    def active_alarms(self):
        return set(self._active)
