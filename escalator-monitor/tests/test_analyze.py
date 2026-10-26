import os, sys, unittest
import numpy as np
import cv2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import analyze

FPS, W, H = 5, 320, 240
MOTION_ROI, PERSON_ROI = (20, 20, 120, 160), (180, 100, 100, 100)


def synth(run_until, person_until, total=60):
    """줄무늬 발판이 run_until초까지 움직이고, 사람(큰 블록)이 person_until초까지 출입 영역을 지나간다."""
    rng = np.random.default_rng(0)
    base = (rng.random((H, W)) * 30 + 100).astype(np.uint8)
    for k in range(int(total * FPS)):
        t = k / FPS
        f = np.stack([base] * 3, -1).copy()
        off = int(t * 12) % 16 if t < run_until else int(run_until * 12) % 16
        for y in range(20, 180, 16):
            cv2.rectangle(f, (20, y + off % 16), (140, y + off % 16 + 6), (30, 30, 30), -1)
        if t < person_until:
            x = 190 + int(t * 7) % 60
            cv2.rectangle(f, (x, 110), (x + 30, 190), (0, 0, 255), -1)
        yield t, f


class AnalyzeTests(unittest.TestCase):
    def test_measures_n(self):
        t, m, p = analyze.extract_series(synth(run_until=40, person_until=12), MOTION_ROI, PERSON_ROI)
        res = analyze.detect(t, m, p)
        self.assertEqual(len(res["stops"]), 1)
        n = res["stops"][0]["n"]
        self.assertIsNotNone(n)
        self.assertAlmostEqual(n, 28, delta=3)  # 정지 40초 - 마지막 사람 12초

    def test_always_running_has_no_stop(self):
        t, m, p = analyze.extract_series(synth(run_until=999, person_until=5), MOTION_ROI, PERSON_ROI)
        self.assertEqual(analyze.detect(t, m, p)["stops"], [])

    def test_plot_and_summary(self):
        t, m, p = analyze.extract_series(synth(40, 12), MOTION_ROI, PERSON_ROI)
        res = analyze.detect(t, m, p)
        out = os.path.join(os.environ.get("TMPDIR", "/tmp"), "plot_test.png")
        analyze.plot(t, res, out)
        self.assertTrue(os.path.getsize(out) > 0)
        self.assertIn("n =", analyze.summarize(res))


if __name__ == "__main__":
    unittest.main()
