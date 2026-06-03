# executor_spec.py

from copy import deepcopy


def build_execution_spec(final_plan: dict) -> dict:
    plan_type = final_plan.get("type")
    resolved = final_plan.get("resolved_device") or {}

    if plan_type != "dns_or_firewall_block":
        return {
            "operation": "unsupported",
            "reason": f"Plan type '{plan_type}' is not enabled yet.",
            "dry_run_supported": True,
            "final_plan": deepcopy(final_plan),
        }

    domains = final_plan.get("domains") or []
    service = final_plan.get("service")
    days = final_plan.get("days") or []
    start_time = final_plan.get("start_time")
    end_time = final_plan.get("end_time")

    if not resolved.get("hostname"):
        raise ValueError("Resolved device hostname is required for execution spec")

    if not domains and not service:
        raise ValueError("Execution spec requires domains or service")

    return {
        "operation": "create_rule",
        "rule_type": "scheduled_domain_block",
        "target": {
            "hostname": resolved.get("hostname"),
            "interface": resolved.get("interface"),
            "ip": resolved.get("ip"),
            "duid": resolved.get("duid"),
            "iaid": resolved.get("iaid"),
        },
        "match": {
            "domains": domains,
            "service": service,
        },
        "schedule": {
            "days": days,
            "start_time": start_time,
            "end_time": end_time,
        },
        "policy": {
            "action": "block",
            "requires_confirmation": True,
        },
        "source_plan_type": plan_type,
        "dry_run_supported": True,
    }