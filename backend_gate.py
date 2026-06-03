from copy import deepcopy


def apply_backend_readiness_gate(exec_spec: dict, prereq_audit: dict, real_apply_probe: dict) -> dict:
    gated = deepcopy(exec_spec)

    checks = (prereq_audit or {}).get("checks", {})
    config_backend_ready = bool(checks.get("true_domain_backend_probe_ready", False))
    real_apply_ready = bool((real_apply_probe or {}).get("ok", False))
    reason = (real_apply_probe or {}).get("reason")

    gated["backend_gate"] = {
        "config_backend_ready": config_backend_ready,
        "dry_run_backend_ready": config_backend_ready,
        "real_apply_ready": real_apply_ready,
        "original_rule_type": exec_spec.get("rule_type"),
        "effective_rule_type": exec_spec.get("rule_type"),
        "fallback_mode": None if real_apply_ready else "dry_run_only",
        "warning": None if real_apply_ready else (
            reason or "Router backend supports planning only; real apply is blocked."
        ),
    }

    return gated
def apply_qos_backend_readiness_gate(exec_spec: dict, qos_probe: dict) -> dict:
    gated = deepcopy(exec_spec)
    checks = (qos_probe or {}).get("checks", {})

    real_apply_ready = bool(checks.get("qos_priority_live_ready", False))
    dry_run_ready = bool(checks.get("qos_priority_dry_run_ready", False))

    gated["backend_gate"] = {
        "config_backend_ready": dry_run_ready,
        "dry_run_backend_ready": dry_run_ready,
        "real_apply_ready": real_apply_ready,
        "original_rule_type": exec_spec.get("rule_type"),
        "effective_rule_type": exec_spec.get("rule_type"),
        "fallback_mode": None if real_apply_ready else "dry_run_only",
        "warning": None if real_apply_ready else "QoS backend is not fully ready for live apply.",
    }
    return gated