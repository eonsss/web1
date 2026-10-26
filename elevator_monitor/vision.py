"""CCTV 프레임 → Observation 값 추출. OpenCV 필요, 사람 검출은 ultralytics(YOLO) 선택."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .config import ElevatorConfig


def crop(frame: np.ndarray, roi: list[float]) -> np.ndarray:
    h, w = frame.shape[:2]
    x, y, rw, rh = roi
    return frame[int(y * h):int((y + rh) * h), int(x * w):int((x + rw) * w)]


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0)


class DoorStateEstimator:
    """문 영역을 '닫힘 기준 이미지'와 비교. 기준은 빈 카 + 문 닫힌 상태에서 한 번 캡처(calibrate).

    사람이 문 앞에 서 있어도 흔들리지 않도록 EMA로 부드럽게 하고 히스테리시스 적용.
    """

    def __init__(self, cfg: ElevatorConfig, closed_ref: Optional[np.ndarray] = None,
                 hi: float = 25.0, lo: float = 12.0):
        self.roi = cfg.door_roi
        self.ref = _gray(crop(closed_ref, self.roi)) if closed_ref is not None else None
        self.hi, self.lo = hi, lo
        self.score = 0.0
        self.open = True

    def set_reference(self, frame: np.ndarray) -> None:
        self.ref = _gray(crop(frame, self.roi))

    def update(self, frame: np.ndarray) -> Optional[bool]:
        if self.ref is None:
            return None
        cur = _gray(crop(frame, self.roi))
        if cur.shape != self.ref.shape:
            cur = cv2.resize(cur, self.ref.shape[::-1])
        diff = float(np.mean(cv2.absdiff(cur, self.ref)))
        self.score = 0.6 * self.score + 0.4 * diff
        if self.open and self.score < self.lo:
            self.open = False
        elif not self.open and self.score > self.hi:
            self.open = True
        return self.open


class SceneryMotion:
    """창밖(6~13호기) 이동 감지: 프레임 간 수직 광학흐름 중앙값의 절댓값.
    카가 움직이면 창밖 전체가 한 방향으로 흐르고, 정지면 ~0."""

    def __init__(self, cfg: ElevatorConfig):
        self.roi = cfg.window_roi
        self.prev: Optional[np.ndarray] = None

    def update(self, frame: np.ndarray) -> Optional[float]:
        if self.roi is None:
            return None
        g = cv2.resize(_gray(crop(frame, self.roi)), (160, 120))
        prev, self.prev = self.prev, g
        if prev is None:
            return 0.0
        flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 2, 15, 2, 5, 1.2, 0)
        return float(abs(np.median(flow[..., 1])) * 30)  # 보정 상수: 현장에서 MOTION_THRESHOLD와 함께 조정


class PersonCounter:
    """카 내부 인원 수. ultralytics가 있으면 YOLO, 없으면 전경(움직이는 영역) 면적 기반 추정."""

    def __init__(self, model: str = "yolov8n.pt", conf: float = 0.4):
        self.conf = conf
        self.yolo = None
        try:
            from ultralytics import YOLO  # type: ignore
            self.yolo = YOLO(model)
        except Exception:
            self.bg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=False)

    def count(self, frame: np.ndarray) -> int:
        if self.yolo is not None:
            res = self.yolo.predict(frame, classes=[0], conf=self.conf, verbose=False)[0]
            return len(res.boxes)
        mask = self.bg.apply(frame)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        area = float(np.count_nonzero(mask)) / mask.size
        return 0 if area < 0.03 else max(1, round(area / 0.15))  # 근사치: 현장 보정 필요
