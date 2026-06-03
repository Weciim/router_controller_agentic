from qosify_catalog import resolve_application_signature


def build_qos_priority_plan(exec_spec: dict, qos_probe: dict | None = None) -> dict:
    target = exec_spec.get("target", {})
    match = exec_spec.get("match", {})
    schedule = exec_spec.get("schedule", {})
    policy = exec_spec.get("policy", {})

    app_name = match.get("application")
    app_sig = resolve_application_signature(app_name)

    hostname = target.get("hostname")
    src_ip = target.get("ip")
    weekdays = schedule.get("days", [])
    start_time = schedule.get("start_time")
    end_time = schedule.get("end_time")

    qos_checks = (qos_probe or {}).get("checks", {})
    live_ready = bool(qos_checks.get("qos_priority_live_ready", False))
    dry_ready = bool(qos_checks.get("qos_priority_dry_run_ready", False))

    return {
        "mode": "scheduled_app_priority",
        "hostname": hostname,
        "src_ip": src_ip,
        "application": app_sig.get("name") if app_sig else app_name,
        "application_signature": app_sig,
        "priority": policy.get("priority") or (app_sig or {}).get("default_priority", "normal"),
        "priority_class": (app_sig or {}).get("priority_class", "besteffort"),
        "days": weekdays,
        "start_time": start_time,
        "end_time": end_time,
        "capability_status": {
            "dry_run_valid": dry_ready,
            "real_apply_ready": live_ready,
            "reason": (
                "Ready for live QoS apply."
                if live_ready
                else "QoS plan preview generated; live apply requires SQM/QoS backend readiness."
            ),
        },
        "notes": [
            "This plan is for app-priority QoS, not domain blocking.",
            "SQM works by controlling the bottleneck and improving latency under congestion.",
            "Application signatures are approximate and may need refinement per app."
        ],
    }