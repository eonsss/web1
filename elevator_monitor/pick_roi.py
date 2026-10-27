"""호기별 문/창밖 영역을 마우스 드래그로 지정해 config에 저장.
사용: python -m elevator_monitor.pick_roi --id 6 [--image 캡처.jpg] [--config config/elevators.json]
 - 영상 소스는 config의 camera(RTSP/파일) 또는 --image. 창이 뜨면 문 → (6~13호기) 창밖 순서로 드래그 후 Enter.
 - 빈 카·문 닫힌 프레임을 refs/ev번호.jpg 로 같이 저장(기준 이미지)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def grab(src: str):
    cap = cv2.VideoCapture(src)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"프레임을 읽지 못했습니다: {src}")
    return frame


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--config", default="config/elevators.json")
    ap.add_argument("--image")
    ap.add_argument("--refs", default="refs")
    a = ap.parse_args()

    path = Path(a.config)
    raw = json.loads(path.read_text(encoding="utf-8"))
    item = next(e for e in raw["elevators"] if e["id"] == a.id)
    frame = cv2.imread(a.image) if a.image else grab(item["camera"])
    h, w = frame.shape[:2]

    def pick(title: str):
        x, y, rw, rh = cv2.selectROI(title, frame, showCrosshair=False)
        cv2.destroyAllWindows()
        return None if rw == 0 or rh == 0 else [round(x / w, 3), round(y / h, 3), round(rw / w, 3), round(rh / h, 3)]

    door = pick(f"{a.id}호기: 문 영역 드래그 후 Enter")
    if door:
        item["door_roi"] = door
    if item.get("see_through"):
        win = pick(f"{a.id}호기: 창밖(유리) 영역 드래그 후 Enter (취소=ESC)")
        if win:
            item["window_roi"] = win
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(a.refs).mkdir(exist_ok=True)
    cv2.imwrite(str(Path(a.refs) / f"ev{a.id:02d}.jpg"), frame)
    print("저장:", item.get("door_roi"), item.get("window_roi"))


if __name__ == "__main__":
    main()
