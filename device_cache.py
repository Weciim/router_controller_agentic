import json
from pathlib import Path

CACHE_PATH = Path("state/device_cache.json")


def _ensure_parent():
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_device_cache() -> list[dict]:
    if not CACHE_PATH.exists():
        return []
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_device_cache(devices: list[dict]) -> None:
    _ensure_parent()
    CACHE_PATH.write_text(json.dumps(devices, indent=2, ensure_ascii=False), encoding="utf-8")


def merge_into_cache(new_devices: list[dict]) -> list[dict]:
    old_devices = load_device_cache()

    merged = {}
    for dev in old_devices + new_devices:
        hostname = (dev.get("hostname") or "").strip().lower()
        ip = (dev.get("ip") or "").strip()
        macaddr = (dev.get("macaddr") or "").strip().lower()
        duid = (dev.get("duid") or "").strip().lower()

        key = hostname or macaddr or duid or ip
        if not key:
            continue

        existing = merged.get(key, {})
        combined = dict(existing)
        combined.update({k: v for k, v in dev.items() if v not in [None, "", []]})
        merged[key] = combined

    result = list(merged.values())
    save_device_cache(result)
    return result


def find_cached_device(target_name: str) -> dict | None:
    target = (target_name or "").strip().lower()
    if not target:
        return None

    for dev in load_device_cache():
        hostname = (dev.get("hostname") or "").strip().lower()
        if hostname == target:
            cached = dict(dev)
            cached["source"] = "device_cache"
            return cached

    return None