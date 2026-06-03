from typing import Dict, Any


def build_execution_plan(validated: Dict[str, Any]) -> Dict[str, Any]:
    intent = validated.get("intent")

    if intent == "schedule_block":
        return {
            "type": "scheduled_domain_block",
            "summary": "Schedule a domain/service block for a target device.",
            "intent": intent,
            "target_device": validated.get("target_device"),
            "target_profile": validated.get("target_profile"),
            "domains": validated.get("domains"),
            "service": validated.get("service"),
            "days": validated.get("days"),
            "start_time": validated.get("start_time"),
            "end_time": validated.get("end_time"),
            "priority": validated.get("priority"),
            "requires_confirmation": validated.get("requires_confirmation", True),
        }

    if intent in {"block_domain", "block_service"}:
        return {
            "type": "domain_block",
            "summary": "Block a domain/service for a target device.",
            "intent": intent,
            "target_device": validated.get("target_device"),
            "target_profile": validated.get("target_profile"),
            "domains": validated.get("domains"),
            "service": validated.get("service"),
            "priority": validated.get("priority"),
            "requires_confirmation": validated.get("requires_confirmation", True),
        }

    if intent == "schedule_priority":
        return {
            "type": "scheduled_app_priority",
            "summary": "Prioritize application traffic for a target device during a scheduled window.",
            "intent": intent,
            "target_device": validated.get("target_device"),
            "target_profile": validated.get("target_profile"),
            "application": validated.get("application") or validated.get("service"),
            "service": validated.get("service"),
            "days": validated.get("days"),
            "start_time": validated.get("start_time"),
            "end_time": validated.get("end_time"),
            "priority": validated.get("priority", "high"),
            "bandwidth_mbps": validated.get("bandwidth_mbps"),
            "requires_confirmation": validated.get("requires_confirmation", True),
        }

    if intent == "reserve_bandwidth":
        return {
            "type": "bandwidth_reservation",
            "summary": "Reserve or prioritize bandwidth for a target device/application.",
            "intent": intent,
            "target_device": validated.get("target_device"),
            "target_profile": validated.get("target_profile"),
            "application": validated.get("application") or validated.get("service"),
            "service": validated.get("service"),
            "days": validated.get("days"),
            "start_time": validated.get("start_time"),
            "end_time": validated.get("end_time"),
            "priority": validated.get("priority", "high"),
            "bandwidth_mbps": validated.get("bandwidth_mbps"),
            "requires_confirmation": validated.get("requires_confirmation", True),
        }

    if intent == "pause_access":
        return {
            "type": "pause_access",
            "summary": "Pause network access for a target.",
            "intent": intent,
            "target_device": validated.get("target_device"),
            "target_profile": validated.get("target_profile"),
            "requires_confirmation": validated.get("requires_confirmation", True),
        }

    if intent == "resume_access":
        return {
            "type": "resume_access",
            "summary": "Resume network access for a target.",
            "intent": intent,
            "target_device": validated.get("target_device"),
            "target_profile": validated.get("target_profile"),
            "requires_confirmation": validated.get("requires_confirmation", True),
        }

    return {
        "type": "unsupported_for_now",
        "summary": f"Unsupported intent: {intent}",
        "intent": intent,
    }