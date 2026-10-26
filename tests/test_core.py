from elevator_monitor.config import ElevatorConfig
from elevator_monitor.core import ElevatorFaultDetector, Level, Observation


def run(see_through, script, **kw):
    """script: [(시각, door_open, people, motion)] 를 1초 간격으로 보간해 입력."""
    cfg = ElevatorConfig(id=1, floors=[1, 5], see_through=see_through, **kw)
    events = []
    det = ElevatorFaultDetector(cfg, events.append)
    for t in range(0, script[-1][0] + 1):
        cur = [s for s in script if s[0] <= t][-1]
        det.update(Observation(float(t), cur[1], cur[2], cur[3]))
    return events


def test_normal_ride_no_alert():
    ev = run(True, [(0, True, 0, 0), (5, True, 1, 0), (8, False, 1, 0),
                    (10, False, 1, 5.0), (30, True, 1, 0), (33, True, 0, 0), (50, True, 0, 0)])
    assert ev == []


def test_short_ride_see_through_no_motion_is_critical():
    ev = run(True, [(0, True, 0, 0), (5, True, 2, 0), (8, False, 2, 0),
                    (11, True, 2, 0), (14, True, 0, 0), (30, True, 0, 0)])
    assert [e.kind for e in ev] == ["SHORT_RIDE"] and ev[0].level is Level.CRITICAL


def test_short_ride_wall_is_warning_then_escalates():
    one = [(0, True, 0, None), (5, True, 1, None), (8, False, 1, None),
           (11, True, 1, None), (14, True, 0, None), (20, True, 0, None)]
    ev = run(False, one)
    assert ev[0].kind == "SHORT_RIDE" and ev[0].level is Level.WARNING
    twice = one + [(400, True, 1, None), (403, False, 1, None), (406, True, 1, None),
                   (409, True, 0, None), (420, True, 0, None)]
    ev = run(False, twice, cooldown_sec=60)
    assert ev[-1].level is Level.CRITICAL


def test_door_reopen_without_exit_is_ignored():
    ev = run(False, [(0, True, 1, None), (3, False, 1, None), (5, True, 1, None),
                     (8, False, 1, None), (30, True, 1, None), (40, True, 0, None), (60, True, 0, None)])
    assert ev == []


def test_boarded_door_never_closes():
    ev = run(False, [(0, True, 0, None), (5, True, 1, None), (30, True, 0, None), (40, True, 0, None)])
    assert [e.kind for e in ev] == ["NO_DOOR_CLOSE"]


def test_stuck_closed_see_through():
    ev = run(True, [(0, True, 1, 0), (3, False, 1, 0), (60, False, 1, 0)])
    assert [e.kind for e in ev] == ["STUCK_CLOSED"] and ev[0].level is Level.CRITICAL


def test_empty_car_door_cycle_is_ignored():
    ev = run(True, [(0, True, 0, 0), (3, False, 0, 0), (6, True, 0, 0), (20, True, 0, 0)])
    assert ev == []
