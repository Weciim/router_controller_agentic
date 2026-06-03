
import json
import os
import uuid
from datetime import datetime

SNAPSHOT_DIR = "snapshots"


def _utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _ensure_dir():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def save_snapshot(kind: str, payload: dict) -> dict:
    _ensure_dir()

    snapshot_id = str(uuid.uuid4())
    ts = _utc_now()
    filename = f"{ts.replace(':', '-').replace('Z', '')}_{kind}_{snapshot_id}.json"
    path = os.path.join(SNAPSHOT_DIR, filename)

    record = {
        "snapshot_id": snapshot_id,
        "kind": kind,
        "created_at": ts,
        "payload": payload,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    return {
        "snapshot_id": snapshot_id,
        "created_at": ts,
        "path": path,
    }