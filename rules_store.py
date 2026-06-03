import json
import os
from typing import Optional
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

RULES_DIR = "rules"
RULES_FILE = os.path.join(RULES_DIR, "rules.json")


def _ensure_store():
    os.makedirs(RULES_DIR, exist_ok=True)
    if not os.path.exists(RULES_FILE):
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump({"rules": []}, f, indent=2)


def load_rules() -> dict:
    _ensure_store()
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rules(data: dict) -> None:
    _ensure_store()
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_rule(rule: dict) -> dict:
    data = load_rules()
    data.setdefault("rules", [])
    data["rules"].append(rule)
    save_rules(data)
    return rule


def get_rule(rule_id: str) -> Optional[dict]:
    data = load_rules()
    for rule in data.get("rules", []):
        if rule.get("rule_id") == rule_id:
            return rule
    return None
RULES_DIR = Path("rules")
RULES_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def store_rule_record(exec_spec: dict, writer_plan: dict, mode: str = "dry_run") -> dict:
    rule_id = str(uuid.uuid4())
    created_at = _utc_now()

    record = {
        "rule_id": rule_id,
        "created_at": created_at,
        "enabled": True,
        "exec_spec": deepcopy(exec_spec),
        "writer_plan": deepcopy(writer_plan),
        "mode": mode,
    }

    path = RULES_DIR / f"{created_at.replace(':', '-')}_{rule_id}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    record["path"] = str(path)
    return record