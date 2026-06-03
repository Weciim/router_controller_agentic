RESERVE_ALIASES = {
    "reserve": "prioritize",
    "reserve_bandwidth": "schedule_priority",
    "guarantee": "prioritize",
    "guarantee_bandwidth": "schedule_priority",
    "boost": "prioritize",
    "prioritize": "prioritize",
}


def normalize_qos_intent(obj: dict) -> dict:
    out = dict(obj or {})

    raw_action = (out.get("action") or "").strip().lower()
    raw_intent = (out.get("intent") or "").strip().lower()

    if raw_action in RESERVE_ALIASES:
        out["action"] = RESERVE_ALIASES[raw_action]

    if raw_intent == "reserve_bandwidth":
        out["intent"] = "schedule_priority"
        if not out.get("priority"):
            out["priority"] = "high"

    if raw_intent == "prioritize":
        out["intent"] = "schedule_priority"

    return out