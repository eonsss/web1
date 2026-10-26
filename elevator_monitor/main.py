"""실행: python -m elevator_monitor.main --config config/elevators.json [--webhook URL] [--only 6 7]
기준 이미지(빈 카, 문 닫힘)는 refs/ev{번호}.jpg 로 두거나 --calibrate 로 저장."""
from __future__ import annotations

import argparse
import logging
import threading
import time
from pathlib import Path

import cv2

from .alerts import Notifier
from .config import ElevatorConfig, load_config
from .core import ElevatorFaultDetector, Observation
from .vision import DoorStateEstimator, PersonCounter, SceneryMotion

log = logging.getLogger("elevator")


def monitor(cfg: ElevatorConfig, notifier: Notifier, refs: Path, stop: threading.Event,
            people: PersonCounter, fps: float = 2.0) -> None:
    ref = cv2.imread(str(refs / f"ev{cfg.id:02d}.jpg"))
    door = DoorStateEstimator(cfg, ref)
    scenery = SceneryMotion(cfg) if cfg.see_through else None
    det = ElevatorFaultDetector(cfg, notifier)
    cap = None
    while not stop.is_set():
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(cfg.camera)
            if not cap.isOpened():
                log.error("%d호기 카메라 연결 실패, 10초 후 재시도", cfg.id)
                stop.wait(10)
                continue
        # 최신 프레임만 사용(버퍼 지연 방지) 후 fps에 맞춰 샘플링
        cap.grab()
        ok, frame = cap.retrieve()
        if not ok:
            cap.release(); cap = None
            continue
        if door.ref is None:
            door.set_reference(frame)  # 기준 이미지가 없으면 첫 프레임을 닫힘 기준으로 가정(권장하지 않음)
        det.update(Observation(
            ts=time.time(),
            door_open=door.update(frame),
            people=people.count(frame),
            scenery_motion=scenery.update(frame) if scenery else None,
        ))
        stop.wait(1.0 / fps)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/elevators.json")
    ap.add_argument("--webhook")
    ap.add_argument("--refs", default="refs")
    ap.add_argument("--only", type=int, nargs="*")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfgs = load_config(a.config)
    notifier = Notifier(a.webhook)
    stop = threading.Event()
    threads = []
    for eid, cfg in cfgs.items():
        if a.only and eid not in a.only:
            continue
        t = threading.Thread(target=monitor, args=(cfg, notifier, Path(a.refs), stop, PersonCounter()), daemon=True)
        t.start(); threads.append(t)
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
