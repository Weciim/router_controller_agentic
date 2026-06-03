from qosify_catalog import _normalize_app_name


def enrich_validated_request_for_priority(validated: dict) -> dict:
    enriched = dict(validated or {})
    intent = enriched.get("intent")
    action = enriched.get("action")
    service = enriched.get("service")
    application = enriched.get("application")

    if intent in {"schedule_priority", "priority"} or action in {"prioritize", "reserve_bandwidth"}:
        enriched["intent"] = "schedule_priority"
        enriched["action"] = "prioritize"

        app_candidate = application or service
        normalized = _normalize_app_name(app_candidate)
        if normalized:
            enriched["application"] = normalized

    return enriched


def build_priority_execution_spec(validated: dict, resolved_device: dict) -> dict:
    return {
        "operation": "create_rule",
        "rule_type": "scheduled_app_priority",
        "target": {
            "hostname": resolved_device.get("hostname"),
            "interface": resolved_device.get("interface"),
            "ip": resolved_device.get("ip"),
            "duid": resolved_device.get("duid"),
            "iaid": resolved_device.get("iaid"),
        },
        "match": {
            "application": validated.get("application"),
            "service": validated.get("service"),
        },
        "schedule": {
            "days": validated.get("days", []),
            "start_time": validated.get("start_time"),
            "end_time": validated.get("end_time"),
        },
        "policy": {
            "action": "prioritize",
            "priority": validated.get("priority", "high"),
            "requires_confirmation": validated.get("requires_confirmation", True),
        },
        "source_plan_type": "qos_priority",
        "dry_run_supported": True,
    }