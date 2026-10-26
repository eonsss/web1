import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from logic import *


def run(mon, timeline, dt=0.5):
    """timeline: [(t, running, riders, events)] 구간 시작 시각 기준의 단계 목록. 발생한 경보를 모아 반환."""
    alarms, end = [], timeline[-1][0] + 60
    steps = timeline + [(end, None, None, ())]
    for (t0, running, riders, ev), (t1, *_ ) in zip(steps, steps[1:]):
        t = t0
        first = True
        while t < t1:
            alarms += mon.update(t, running, riders, ev if first else ())
            first, t = False, t + dt
    return alarms


def raised(alarms):
    return [a.code for a in alarms if a.raised]


class StandbyTests(unittest.TestCase):
    def mon(self, **kw):
        return Monitor("E1", Config(stop_delay_s=30, stop_tolerance_s=5, start_grace_s=5, confirm_s=2, **kw))

    def test_normal_forward_ride_no_alarm(self):
        a = run(self.mon(), [
            (0, False, 0, ()),
            (10, False, 1, (ENTER_FWD,)),   # 탑승, 기동 지연 3초
            (13, True, 1, ()),
            (25, True, 0, (EXIT_FWD,)),     # 하차
            (25 + 30, False, 0, ()),        # 30초 뒤 정지 (정상)
        ])
        self.assertEqual(raised(a), [])

    def test_early_stop_after_exit(self):
        a = run(self.mon(), [
            (0, True, 1, ()), (10, True, 0, (EXIT_FWD,)), (15, False, 0, ()),  # 5초 만에 정지
        ])
        self.assertEqual(raised(a), [Code.EARLY_STOP])

    def test_stuck_running(self):
        a = run(self.mon(), [(0, True, 1, ()), (10, True, 0, (EXIT_FWD,))])  # 계속 운행
        self.assertEqual(raised(a), [Code.STUCK_RUNNING])

    def test_stop_within_tolerance_ok(self):
        a = run(self.mon(), [(0, True, 1, ()), (10, True, 0, (EXIT_FWD,)), (10 + 27, False, 0, ())])
        self.assertEqual(raised(a), [])

    def test_ride_stopped_is_critical(self):
        a = run(self.mon(), [(0, True, 2, ()), (10, False, 2, ())])
        self.assertEqual(raised(a), [Code.RIDE_STOPPED])
        self.assertEqual(a[0].severity, "critical")

    def test_fail_to_start_forward(self):
        a = run(self.mon(), [(0, False, 0, ()), (10, False, 1, (ENTER_FWD,))])
        self.assertEqual(raised(a), [Code.FAIL_TO_START])

    def test_reverse_entry_moving_is_ok(self):
        a = run(self.mon(), [(0, False, 0, ()), (10, False, 1, (ENTER_REV,)), (12, True, 1, ()),
                             (20, True, 0, (EXIT_REV,)), (30, False, 0, ())])
        self.assertEqual(raised(a), [])

    def test_reverse_entry_not_moving_is_fault(self):
        a = run(self.mon(), [(0, False, 0, ()), (10, False, 1, (ENTER_REV,))])
        self.assertEqual(raised(a), [Code.FAIL_TO_START])

    def test_new_rider_cancels_stop_timer(self):
        a = run(self.mon(), [(0, True, 1, ()), (10, True, 0, (EXIT_FWD,)),
                             (20, True, 1, (ENTER_FWD,)), (30, True, 0, (EXIT_FWD,)), (30 + 30, False, 0, ())])
        self.assertEqual(raised(a), [])

    def test_glitch_shorter_than_confirm_ignored(self):
        a = run(self.mon(), [(0, True, 1, ()), (10, False, 1, ()), (11, True, 1, ())])
        self.assertEqual(raised(a), [])

    def test_alarm_clears_on_recovery(self):
        a = run(self.mon(), [(0, True, 1, ()), (10, False, 1, ()), (20, True, 1, ())])
        self.assertEqual([x.raised for x in a], [True, False])

    def test_maintenance_suppresses(self):
        m = self.mon(); m.maintenance = True
        self.assertEqual(run(m, [(0, True, 1, ()), (10, False, 1, ())]), [])


class AlwaysOnTests(unittest.TestCase):
    def test_stopped_without_riders_alarms(self):
        m = Monitor("E2", Config(mode=Mode.ALWAYS_ON))
        self.assertEqual(raised(run(m, [(0, True, 0, ()), (10, False, 0, ())])), [Code.STOPPED_ALWAYS_ON])

    def test_running_without_riders_ok(self):
        m = Monitor("E2", Config(mode=Mode.ALWAYS_ON))
        self.assertEqual(run(m, [(0, True, 0, ()), (100, True, 0, ())]), [])


if __name__ == "__main__":
    unittest.main()
