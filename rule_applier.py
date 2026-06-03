from datetime import datetime
import uuid

from rules_store import add_rule, get_rule
from domain_block_writer import build_scheduled_domain_block_plan


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def apply_execution_spec(exec_spec: dict, client, dry_run: bool = True) -> dict:
    rule_type = exec_spec.get("rule_type")
    backend_gate = exec_spec.get("backend_gate", {})

    dry_run_backend_ready = backend_gate.get("dry_run_backend_ready", False)
    real_apply_ready = backend_gate.get("real_apply_ready", False)
    warning = backend_gate.get("warning")
    fallback_mode = backend_gate.get("fallback_mode")

    if rule_type == "scheduled_domain_block":
        if dry_run:
            if not dry_run_backend_ready:
                return {
                    "applied": False,
                    "mode": "blocked_before_writer",
                    "dry_run": True,
                    "operation": exec_spec.get("operation"),
                    "rule_type": rule_type,
                    "reason": warning or "Dry-run backend is not ready for this rule type.",
                    "backend_gate": backend_gate,
                }

            writer_result = build_scheduled_domain_block_plan(exec_spec, client)
            plan = writer_result["plan"]
            plan["capability_status"] = {
                "dry_run_valid": True,
                "real_apply_ready": real_apply_ready,
                "reason": warning or (
                    "Plan preview generated successfully."
                    if real_apply_ready
                    else "Router backend is preview-only for this rule."
                ),
            }

            rule = {
                "rule_id": str(uuid.uuid4()),
                "created_at": _utc_now(),
                "enabled": True,
                "exec_spec": exec_spec,
                "writer_plan": plan,
                "mode": "dry_run",
            }

            add_rule(rule)

            return {
                "applied": False,
                "mode": "openwrt_dry_run_and_store",
                "dry_run": True,
                "operation": exec_spec.get("operation"),
                "rule_type": rule_type,
                "backend_gate": backend_gate,
                "writer_result": {
                    "applied": False,
                    "dry_run": True,
                    "applied_at": _utc_now(),
                    "plan": plan,
                },
                "rule": rule,
            }

        if not real_apply_ready:
            return {
                "applied": False,
                "mode": "blocked_real_apply",
                "dry_run": False,
                "operation": exec_spec.get("operation"),
                "rule_type": rule_type,
                "reason": warning or "Real apply is blocked by backend capability.",
                "backend_gate": backend_gate,
            }

        writer_result = build_scheduled_domain_block_plan(exec_spec, client)
        plan = writer_result["plan"]

        rule = {
            "rule_id": str(uuid.uuid4()),
            "created_at": _utc_now(),
            "enabled": True,
            "exec_spec": exec_spec,
            "writer_plan": plan,
            "mode": "apply",
        }

        add_rule(rule)

        return {
            "applied": False,
            "mode": "real_apply_not_implemented_yet",
            "dry_run": False,
            "operation": exec_spec.get("operation"),
            "rule_type": rule_type,
            "reason": "Real apply path is allowed by backend gate, but execution is not implemented yet.",
            "backend_gate": backend_gate,
            "rule": rule,
            "writer_result": {
                "applied": False,
                "dry_run": False,
                "applied_at": _utc_now(),
                "plan": plan,
            },
        }

    raise NotImplementedError(
        f"apply_execution_spec() does not yet handle rule_type={rule_type!r}"
    )


def verify_applied_rule(apply_result: dict) -> dict:
    rule = apply_result.get("rule") or {}
    rule_id = rule.get("rule_id")

    if apply_result.get("mode") == "blocked_real_apply":
        return {
            "verified": False,
            "dry_run": False,
            "rule_id": None,
            "reason": apply_result.get("reason", "Real apply was blocked."),
        }

    if apply_result.get("mode") == "blocked_before_writer":
        return {
            "verified": False,
            "dry_run": True,
            "rule_id": None,
            "reason": apply_result.get("reason", "Dry-run generation was blocked."),
        }

    if not rule_id:
        return {
            "verified": False,
            "reason": "No rule_id present after apply.",
        }

    stored = get_rule(rule_id)
    if not stored:
        return {
            "verified": False,
            "reason": f"Rule {rule_id} not found in store after apply.",
        }

    if apply_result.get("dry_run"):
        return {
            "verified": True,
            "dry_run": True,
            "rule_id": rule_id,
            "stored_rule": stored,
            "reason": "Dry run preview stored successfully.",
        }

    writer_result = apply_result.get("writer_result") or {}
    verification = writer_result.get("verification", "")

    return {
        "verified": True,
        "dry_run": False,
        "rule_id": rule_id,
        "stored_rule": stored,
        "router_verification": verification,
    }