# rollback_store.py

import json
import os
import uuid
from datetime import datetime

ROLLBACK_DIR = "rollback"


def _utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _ensure_dir():
    os.makedirs(ROLLBACK_DIR, exist_ok=True)


def save_rollback_record(payload: dict) -> dict:
    _ensure_dir()

    rollback_id = str(uuid.uuid4())
    ts = _utc_now()
    filename = f"{ts.replace(':', '-').replace('Z', '')}_rollback_{rollback_id}.json"
    path = os.path.join(ROLLBACK_DIR, filename)

    record = {
        "rollback_id": rollback_id,
        "created_at": ts,
        "payload": payload,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    return {
        "rollback_id": rollback_id,
        "created_at": ts,
        "path": path,
    }