"""Session debug NDJSON (debug mode); do not log secrets."""

from __future__ import annotations

import json
import time
from pathlib import Path

# .../test/backend/app/this_file.py -> parents[1] == repo root (test/)
_WS_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = _WS_ROOT / "debug-5fe07f.log"
SESSION = "5fe07f"


def agent_dbg(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    *,
    run_id: str = "run1",
) -> None:
    try:
        line = json.dumps(
            {
                "sessionId": SESSION,
                "runId": run_id,
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data or {},
                "timestamp": int(time.time() * 1000),
            },
            ensure_ascii=False,
        )
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
