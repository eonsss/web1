import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from logic import Mode


class ConfigTests(unittest.TestCase):
    def test_loads_22_with_expected_modes(self):
        mons, unmeasured, items = config.load(os.path.join(os.path.dirname(__file__), "..", "escalators.json"))
        self.assertEqual(len(mons), 22)
        always = sorted(i for i, m in mons.items() if m.cfg.mode is Mode.ALWAYS_ON)
        self.assertEqual(always, [2, 17, 18, 19])
        self.assertEqual(len(unmeasured), 18)  # 절전형은 n 측정 전


if __name__ == "__main__":
    unittest.main()
