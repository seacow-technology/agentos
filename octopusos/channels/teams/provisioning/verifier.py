from __future__ import annotations

import time
from pathlib import Path
from typing import Dict


def verify_trace_chain(log_path: str) -> Dict[str, object]:
    path = Path(log_path)
    if not path.exists():
        return {
            "ok": False,
            "error": "log_not_found",
            "checks": {
                "teams_inbound_trace": False,
                "teams_send_trace": False,
                "chat_reply_sent": False,
            },
        }

    text = path.read_text(encoding="utf-8", errors="ignore")
    checks = {
        "teams_inbound_trace": "teams_inbound_trace" in text,
        "teams_send_trace": "teams_send_trace" in text,
        "chat_reply_sent": "chat_reply_sent" in text,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
    }


def wait_for_trace_chain(log_path: str, *, timeout_sec: int = 30, poll_interval_sec: float = 1.0) -> Dict[str, object]:
    deadline = time.time() + max(int(timeout_sec), 1)
    last = verify_trace_chain(log_path)
    if bool(last.get("ok")):
        return {**last, "timed_out": False, "waited_sec": 0}

    while time.time() < deadline:
        time.sleep(max(float(poll_interval_sec), 0.1))
        last = verify_trace_chain(log_path)
        if bool(last.get("ok")):
            waited = max(0, int(timeout_sec - max(0, deadline - time.time())))
            return {**last, "timed_out": False, "waited_sec": waited}

    return {
        **last,
        "ok": False,
        "error": str(last.get("error") or "verification_timeout"),
        "timed_out": True,
        "waited_sec": int(timeout_sec),
    }
