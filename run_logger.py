# run_logger.py

import json
import os
from datetime import datetime


LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "router_runs.jsonl")


def log_event(stage: str, payload: dict):
    os.makedirs(LOG_DIR, exist_ok=True)

    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "stage": stage,
        "payload": payload,
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")