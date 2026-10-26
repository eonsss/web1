"""영상 분석 도구: 영상 파일에서 에스컬레이터 운행/정지와 사람 유무를 시계열로 뽑고,
'마지막 사람이 사라진 시각 -> 정지 시각'(n)을 계산한다.

사용: analyze.exe [영상파일]   (파일을 안 주면 선택 창이 뜬다)
  1) 첫 화면에서 '운행 판정 영역'(핸드레일/발판 일부)을 드래그 후 Enter
  2) 이어서 '사람 출입 영역'(하차 지점 바닥)을 드래그 후 Enter
결과는 영상 파일 옆에 _analysis.csv / _analysis.png / _summary.txt 로 저장된다.
"""
import csv, os, sys
import cv2
import numpy as np

WIDTH = 640          # 분석용 해상도 (가로)
ANALYSIS_FPS = 5     # 초당 분석 프레임 수
SMOOTH_S = 1.0       # 평활화 구간
MIN_PRESENCE = 0.03  # 출입 영역에서 배경과 다른 픽셀 비율이 이 이상이면 '사람 있음'
PERSON_DIFF = 40     # 배경과의 밝기 차이가 이 이상이면 다른 픽셀로 센다


def _crop(frame, roi):
    x, y, w, h = roi
    return frame[y:y + h, x:x + w]


def _smooth(x, n):
    n = max(1, int(n))
    pad = np.pad(x, (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(pad, np.ones(n) / n, mode="valid")


def extract_series(frames, motion_roi, person_roi):
    """frames: (t_sec, BGR 프레임) 반복자. 반환: t, motion(광학흐름 크기), presence(배경과 다른 픽셀 비율).

    사람 유무는 영상 전체의 중앙값을 빈 바닥 배경으로 삼아 비교한다(고정 카메라, 오프라인 분석).
    서 있는 사람이 배경으로 흡수되는 문제를 피하려는 것이므로, 사람이 영상의 절반 이상 계속 있으면 부정확하다."""
    prev, t, motion, crops = None, [], [], []
    for ts, frame in frames:
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        g = _crop(gray, motion_roi)
        if prev is not None:
            flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 2, 15, 2, 5, 1.1, 0)
            m = float(np.mean(np.hypot(flow[..., 0], flow[..., 1])))
        else:
            m = 0.0
        prev = g
        t.append(ts); motion.append(m); crops.append(_crop(gray, person_roi))
    bg = np.median(np.stack(crops), axis=0)
    presence = [float(np.mean(np.abs(c.astype(np.int16) - bg) > PERSON_DIFF)) for c in crops]
    return np.array(t), np.array(motion), np.array(presence)


def detect(t, motion, presence, thr=None):
    """운행 여부(히스테리시스)와 사람 유무를 판정하고, 정지 시점별 n을 계산한다."""
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0
    n = SMOOTH_S / dt
    m = _smooth(motion, n)
    p = _smooth(presence, n)
    if thr is None:
        lo, hi = np.percentile(m, 10), np.percentile(m, 90)
        thr = (lo + hi) / 2 if hi - lo > 0.05 else None   # 구분이 안 되면 판정 불가
    running = np.zeros(len(t), bool)
    if thr is not None:
        state = False
        for i, v in enumerate(m):
            state = v > thr * 1.2 if not state else v > thr * 0.8
            running[i] = state
    person = p > MIN_PRESENCE
    events = []
    for i in range(1, len(t)):
        if running[i - 1] and not running[i]:
            last = next((j for j in range(i, -1, -1) if person[j]), None)
            events.append({"stop_t": t[i], "last_person_t": None if last is None else t[last],
                           "n": None if last is None else t[i] - t[last]})
    starts = [t[i] for i in range(1, len(t)) if not running[i - 1] and running[i]]
    return {"thr": thr, "running": running, "person": person, "stops": events, "starts": starts, "m": m, "p": p}


def read_frames(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, round(fps / ANALYSIS_FPS))
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            h = int(f.shape[0] * WIDTH / f.shape[1])
            yield i / fps, cv2.resize(f, (WIDTH, h))
        i += 1
    cap.release()


def plot(t, res, path):
    W, H = 1000, 420
    img = np.full((H, W, 3), 255, np.uint8)
    t0, t1 = float(t[0]), float(t[-1]) or 1.0
    X = lambda v: int(50 + (v - t0) / max(t1 - t0, 1e-9) * (W - 70))
    def trace(y, ymax, top, bot, color):
        pts = [(X(a), int(bot - min(b / max(ymax, 1e-9), 1) * (bot - top))) for a, b in zip(t, y)]
        cv2.polylines(img, [np.array(pts, np.int32)], False, color, 1)
    trace(res["m"], max(res["m"].max(), 1e-6), 30, 190, (200, 80, 0))
    if res["thr"] is not None:
        ty = int(190 - res["thr"] / max(res["m"].max(), 1e-6) * 160)
        cv2.line(img, (50, ty), (W - 20, ty), (0, 0, 200), 1)
    trace(res["p"], max(res["p"].max(), 1e-6), 230, 390, (0, 140, 0))
    for e in res["stops"]:
        cv2.line(img, (X(e["stop_t"]), 20), (X(e["stop_t"]), 400), (0, 0, 255), 1)
    cv2.putText(img, "motion (blue) / threshold (red) / stop (red line)", (50, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.putText(img, "person presence (green)", (50, 222), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.putText(img, f"{t0:.0f}s", (45, 412), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.putText(img, f"{t1:.0f}s", (W - 60, 412), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.imencode(".png", img)[1].tofile(path)  # 한글 경로 대응


def summarize(res):
    lines = [f"운행 판정 임계값: {res['thr'] if res['thr'] is None else round(res['thr'], 3)}"]
    if res["thr"] is None:
        lines.append("운행/정지 구분이 안 되는 영상입니다(움직임 변화가 거의 없음). 영역을 다시 지정하거나 PNG를 확인하세요.")
    lines.append("기동 시각(초): " + (", ".join(f"{s:.1f}" for s in res["starts"]) or "없음"))
    for e in res["stops"]:
        n = "사람 감지 없음" if e["n"] is None else f"n = {e['n']:.1f}초 (마지막 사람 {e['last_person_t']:.1f}초 -> 정지 {e['stop_t']:.1f}초)"
        lines.append(f"정지 시각 {e['stop_t']:.1f}초: {n}")
    if not res["stops"]:
        lines.append("영상 중 정지 전환이 감지되지 않았습니다.")
    return "\n".join(lines)


def select_roi(frame, title):
    win = f"{title} - drag then ENTER (ESC=cancel)"
    roi = cv2.selectROI(win, frame, showCrosshair=False)
    cv2.destroyAllWindows()
    if roi[2] == 0 or roi[3] == 0:
        raise SystemExit("영역이 선택되지 않아 종료합니다.")
    return roi


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        import tkinter as tk
        from tkinter import filedialog
        tk.Tk().withdraw()
        path = filedialog.askopenfilename(title="분석할 영상 선택", filetypes=[("video", "*.mp4 *.avi *.mkv *.mov"), ("all", "*.*")])
    if not path:
        return
    frames = list(read_frames(path))
    if len(frames) < 10:
        raise SystemExit("영상을 읽을 수 없거나 너무 짧습니다.")
    first = frames[0][1]
    motion_roi = select_roi(first, "1) MOTION area: handrail / steps")
    person_roi = select_roi(first, "2) PERSON area: floor where people step off")
    t, m, p = extract_series(iter(frames), motion_roi, person_roi)
    res = detect(t, m, p)
    base = os.path.splitext(path)[0]
    with open(base + "_analysis.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_sec", "motion", "presence", "running", "person"])
        for row in zip(t, res["m"], res["p"], res["running"].astype(int), res["person"].astype(int)):
            w.writerow([f"{row[0]:.2f}", f"{row[1]:.4f}", f"{row[2]:.4f}", row[3], row[4]])
    plot(t, res, base + "_analysis.png")
    text = summarize(res)
    with open(base + "_summary.txt", "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print("\n저장됨:", base + "_analysis.csv / .png / _summary.txt")
    if len(sys.argv) <= 1:
        input("Enter 키를 누르면 종료합니다.")


if __name__ == "__main__":
    main()
