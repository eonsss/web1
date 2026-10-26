import numpy as np

from elevator_monitor.config import ElevatorConfig
from elevator_monitor.vision import DoorStateEstimator, SceneryMotion


def cfg():
    return ElevatorConfig(id=6, floors=[1, 1], see_through=True, window_roi=[0, 0, 0.5, 0.5])


def test_door_state():
    closed = np.full((240, 320, 3), 120, np.uint8)
    d = DoorStateEstimator(cfg(), closed)
    for _ in range(5):
        assert d.update(closed) is False
    opened = closed.copy(); opened[:, 96:224] = 20
    for _ in range(5):
        r = d.update(opened)
    assert r is True


def test_scenery_motion_detects_scroll():
    rng = np.random.default_rng(0)
    base = rng.integers(0, 255, (480, 640), np.uint8)
    base = np.stack([base] * 3, -1)
    s = SceneryMotion(cfg())
    s.update(base)
    still = s.update(base)
    moved = s.update(np.roll(base, 12, axis=0))
    assert still < 0.5 < moved
