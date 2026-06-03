from typing import Any, Dict, List, Optional


ALLOWED_INTENTS = {
    "schedule_block",
    "schedule_priority",
    "reserve_bandwidth",
    "pause_access",
    "resume_access",
    "set_time_limit",
    "block_category",
    "block_domain",
    "block_service",
    "clarify_request",
    "reject_or_review",
    "prioritize",
}

ALLOWED_ACTIONS = {
    "block",
    "reserve_bandwidth",
    "prioritize",
    "pause",
    "resume",
    "allow_only_during_window",
    "ask_clarification",
    "reject",
}

ALLOWED_STATUS = {
    "ok",
    "needs_clarification",
    "unsafe",
    "conflict",
    "unsupported",
}

ALLOWED_PRIORITIES = {"low", "normal", "medium", "high", "critical"}

DAY_ALIASES = {
    "weekday": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "weekend": ["Sat", "Sun"],
    "weekends": ["Sat", "Sun"],
    "daily": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "everyday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

VALID_DAY_NAMES = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}


class ValidationError(Exception):
    pass


def _at_least_one_target(obj):
    return obj["target_device"] is not None or obj["target_profile"] is not None


def _has_time_window(obj):
    return obj["start_time"] is not None and obj["end_time"] is not None


def _is_str_or_none(x):
    return isinstance(x, str) or x is None


def _is_bool(x):
    return isinstance(x, bool)


def _is_int_or_none(x):
    return isinstance(x, int) or x is None


def _is_str_list_or_none(x):
    if x is None:
        return True
    return isinstance(x, list) and all(isinstance(i, str) and i.strip() for i in x)


def _normalize_time_str(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be string or null")

    text = value.strip()
    parts = text.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValidationError(f"{field_name} must be in HH:MM format")

    hh, mm = map(int, parts)
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValidationError(f"{field_name} has invalid time value")

    return f"{hh:02d}:{mm:02d}"


def _normalize_days(days: Optional[List[str]]) -> Optional[List[str]]:
    if days is None:
        return None

    normalized: List[str] = []
    for day in days:
        text = day.strip()
        lowered = text.lower()

        if lowered in DAY_ALIASES:
            normalized.extend(DAY_ALIASES[lowered])
        elif text in VALID_DAY_NAMES:
            normalized.append(text)
        else:
            raise ValidationError(f"Invalid day value: {day}")

    deduped: List[str] = []
    seen = set()
    for day in normalized:
        if day not in seen:
            deduped.append(day)
            seen.add(day)

    return deduped


def validate_router_output(obj: Dict[str, Any]) -> Dict[str, Any]:
    required_keys = [
        "intent", "action", "target_device", "target_profile", "service",
        "domains", "category", "days", "start_time", "end_time",
        "duration_minutes", "priority", "bandwidth_mbps",
        "requires_confirmation", "needs_clarification",
        "clarification_question", "status"
    ]

    missing = [k for k in required_keys if k not in obj]
    extra = [k for k in obj.keys() if k not in required_keys]

    if missing:
        raise ValidationError(f"Missing keys: {missing}")
    if extra:
        raise ValidationError(f"Unexpected keys: {extra}")

    if obj["intent"] not in ALLOWED_INTENTS:
        raise ValidationError(f"Invalid intent: {obj['intent']}")
    if obj["action"] not in ALLOWED_ACTIONS:
        raise ValidationError(f"Invalid action: {obj['action']}")
    if obj["status"] not in ALLOWED_STATUS:
        raise ValidationError(f"Invalid status: {obj['status']}")

    if obj["priority"] is not None:
        obj["priority"] = str(obj["priority"]).strip().lower()
        if obj["priority"] not in ALLOWED_PRIORITIES:
            raise ValidationError(f"Invalid priority: {obj['priority']}")

    for key in ["target_device", "target_profile", "service", "category", "clarification_question"]:
        if not _is_str_or_none(obj[key]):
            raise ValidationError(f"{key} must be string or null")

    for key in ["domains", "days"]:
        if not _is_str_list_or_none(obj[key]):
            raise ValidationError(f"{key} must be list[str] or null")

    for key in ["duration_minutes", "bandwidth_mbps"]:
        if not _is_int_or_none(obj[key]):
            raise ValidationError(f"{key} must be int or null")

    for key in ["requires_confirmation", "needs_clarification"]:
        if not _is_bool(obj[key]):
            raise ValidationError(f"{key} must be boolean")

    obj["start_time"] = _normalize_time_str(obj["start_time"], "start_time")
    obj["end_time"] = _normalize_time_str(obj["end_time"], "end_time")
    obj["days"] = _normalize_days(obj["days"])

    if obj["duration_minutes"] is not None and obj["duration_minutes"] <= 0:
        raise ValidationError("duration_minutes must be > 0")

    if obj["bandwidth_mbps"] is not None and obj["bandwidth_mbps"] <= 0:
        raise ValidationError("bandwidth_mbps must be > 0")

    if obj["target_device"] and obj["target_profile"]:
        raise ValidationError("Only one of target_device or target_profile should be set")

    if obj["intent"] == "clarify_request":
        if not obj["needs_clarification"]:
            raise ValidationError("clarify_request must set needs_clarification=True")
        if not obj["clarification_question"]:
            raise ValidationError("clarify_request must include clarification_question")

    if obj["status"] == "needs_clarification" and not obj["needs_clarification"]:
        raise ValidationError("status=needs_clarification requires needs_clarification=True")

    if not _at_least_one_target(obj) and obj["intent"] not in {"clarify_request", "reject_or_review"}:
        raise ValidationError("A target_device or target_profile is required")

    if obj["intent"] in {"block_domain", "schedule_block"}:
        if obj["domains"] is None and obj["service"] is None:
            raise ValidationError("blocking actions need domains or service")
        obj["action"] = "block"
        if obj["intent"] == "schedule_block" and not _has_time_window(obj):
            raise ValidationError("schedule_block requires start_time and end_time")

    elif obj["intent"] == "block_service":
        if obj["service"] is None:
            raise ValidationError("block_service requires service")
        obj["action"] = "block"

    elif obj["intent"] in {"prioritize", "schedule_priority"}:
        if obj["service"] is None:
            raise ValidationError("priority actions require service")
        obj["intent"] = "schedule_priority"
        obj["action"] = "prioritize"
        if obj["priority"] is None:
            obj["priority"] = "high"

    elif obj["intent"] == "reserve_bandwidth":
        if obj["service"] is None and obj["bandwidth_mbps"] is None:
            raise ValidationError("reserve_bandwidth requires service or bandwidth_mbps")
        if obj["action"] not in {"reserve_bandwidth", "prioritize"}:
            obj["action"] = "reserve_bandwidth"
        if obj["priority"] is None:
            obj["priority"] = "high"

    elif obj["intent"] == "pause_access":
        obj["action"] = "pause"

    elif obj["intent"] == "resume_access":
        obj["action"] = "resume"

    return obj