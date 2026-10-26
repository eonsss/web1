"""알림 전송: 콘솔/로그 + (선택) 웹훅(방재실 모니터링 PC·메신저 등)."""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Optional

from .core import FaultEvent

log = logging.getLogger("elevator")


class Notifier:
    def __init__(self, webhook_url: Optional[str] = None, log_path: str = "faults.jsonl"):
        self.webhook_url = webhook_url
        self.log_path = log_path

    def __call__(self, ev: FaultEvent) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ev.ts))
        msg = f"[{ev.level.value}] {ev.elevator_id}호기 고장 의심({ev.kind}) {stamp} - {ev.detail}"
        log.warning(msg)
        rec = {"elevator": ev.elevator_id, "ts": ev.ts, "kind": ev.kind, "level": ev.level.value, "detail": ev.detail}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if self.webhook_url:
            try:
                req = urllib.request.Request(
                    self.webhook_url, json.dumps({"text": msg}).encode(),
                    {"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:  # 알림 실패가 감시를 멈추면 안 됨
                log.error("webhook 실패: %s", e)
