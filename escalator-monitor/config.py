"""escalators.json 로더. 값이 null인 항목은 defaults로 대체하고, 측정이 필요한 호기를 알려준다."""
import json
from logic import Config, Mode, Monitor


def load(path="escalators.json"):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    d = raw["defaults"]
    monitors, unmeasured = {}, []
    for e in raw["escalators"]:
        mode = Mode(e["mode"])
        cfg = Config(
            mode=mode,
            stop_delay_s=e.get("stop_delay_s") or d["stop_delay_s"],
            stop_tolerance_s=d["stop_tolerance_s"],
            start_grace_s=e.get("start_grace_s") or d["start_grace_s"],
            confirm_s=d["confirm_s"],
        )
        if mode is Mode.STANDBY and not (e.get("stop_delay_s") and e.get("start_grace_s")):
            unmeasured.append(e["name"])
        monitors[e["id"]] = Monitor(e["name"], cfg)
    return monitors, unmeasured, raw["escalators"]
