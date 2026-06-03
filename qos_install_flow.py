def should_offer_qos_install(qos_probe: dict, qos_diag: dict) -> bool:
    if not qos_probe:
        return False
    checks = qos_probe.get("checks", {})
    if checks.get("qos_priority_live_ready", False):
        return False
    diag_checks = (qos_diag or {}).get("checks", {})
    return bool(
        diag_checks.get("qosify_available")
        or diag_checks.get("sqm_available")
        or diag_checks.get("tc_full_available")
    )


def summarize_qos_install_need(qos_probe: dict, qos_diag: dict) -> dict:
    probe_checks = (qos_probe or {}).get("checks", {})
    diag_checks = (qos_diag or {}).get("checks", {})
    return {
        "live_ready": bool(probe_checks.get("qos_priority_live_ready", False)),
        "qosify_available": bool(diag_checks.get("qosify_available", False)),
        "sqm_available": bool(diag_checks.get("sqm_available", False)),
        "tc_full_available": bool(diag_checks.get("tc_full_available", False)),
        "recommended_backend": qos_diag.get("preferred_backend"),
        "can_attempt_install_now": should_offer_qos_install(qos_probe, qos_diag),
    }