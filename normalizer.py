def normalize_router_output(obj: dict) -> dict:
    obj = dict(obj)

    if obj.get("intent") == "block":
        if obj.get("days") or obj.get("start_time") or obj.get("end_time"):
            obj["intent"] = "schedule_block"
        elif obj.get("domains"):
            obj["intent"] = "block_domain"

    if obj.get("action") == "block" and obj.get("intent") in {"block_domain", "schedule_block"}:
        obj["status"] = obj.get("status") or "ok"

    if obj.get("days"):
        obj["days"] = [d.strip().lower() for d in obj["days"] if isinstance(d, str) and d.strip()]

    if obj.get("priority") and isinstance(obj["priority"], str):
        obj["priority"] = obj["priority"].strip().lower()

    if obj.get("target_device") and isinstance(obj["target_device"], str):
        obj["target_device"] = obj["target_device"].strip()

    if obj.get("service") and isinstance(obj["service"], str):
        obj["service"] = obj["service"].strip().lower()

    return obj