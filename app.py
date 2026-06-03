import json
import os
import traceback
from datetime import datetime
from flask import Flask, jsonify, render_template, request

from validator import validate_router_output, ValidationError
from planner import build_execution_plan
from openwrt_client import OpenWrtClient
from resolver import (
    resolve_target_device,
    build_clarification_response,
    enrich_plan_with_device,
)
from executor_spec import build_execution_spec
from llm_parser import parse_prompt_to_router_json, warmup_model
from normalizer import normalize_router_output
from run_logger import log_event
from rules_store import load_rules
from snapshot_store import save_snapshot
from rollback_store import save_rollback_record
from apply_execution_spec import apply_execution_spec
from capability_probe import probe_router_capabilities
from prereq_audit import build_prereq_audit
from backend_gate import (
    apply_backend_readiness_gate,
    apply_qos_backend_readiness_gate,
)
from device_discovery import discover_devices
from device_inventory import get_all_available_devices
from device_cache import find_cached_device, merge_into_cache
from ssh_client import OpenWrtSSHClient
from real_apply_gate import check_router_real_apply_readiness
from package_diagnostics import diagnose_dnsmasq_packages
from dnsmasq_remediation import build_dnsmasq_remediation_plan
from feed_diagnostics import diagnose_apk_feeds
from status_summary import summarize_backend_status
from dnsmasq_installer import build_dnsmasq_full_upgrade_plan
from apply_guard import ensure_real_apply_allowed
from priority_intent_support import (
    enrich_validated_request_for_priority,
    build_priority_execution_spec,
)
from qos_capability_probe import probe_qos_capabilities
from qos_package_diagnostics import diagnose_qos_packages
from qos_fix_planner import build_qos_install_plan
from qos_install_flow import summarize_qos_install_need
from qosify_catalog import resolve_application_signature
from qosify_live_plan import build_qosify_live_plan
from qosify_live_executor import execute_qosify_live_plan
from intent_normalizer import normalize_qos_intent
from verify_qosify import verify_qosify_result
from ssh_result_utils import run_ssh_normalized
from cron_capability import detect_scheduler_backend
from apply_schedule_plan import apply_qosify_schedule_plan
from qosify_schedule_plan import build_qosify_schedule_plan as build_runtime_qosify_schedule_plan
from supported_apps import list_supported_apps, list_supported_aliases

DRY_RUN_RULES = os.getenv("DRY_RUN_RULES", "true").lower() == "true"
DRY_RUN_PACKAGES = os.getenv("DRY_RUN_PACKAGES", "false").lower() == "true"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

_state = {
    "warmed_up": False,
    "last_bootstrap": None,
}


def safe_log(name, payload):
    try:
        log_event(name, payload)
    except Exception:
        pass


def build_clients():
    router_host = os.getenv("ROUTER_HOST", "192.168.56.2")
    router_user = os.getenv("ROUTER_USER", "root")
    router_password = os.getenv("ROUTER_PASSWORD")

    ssh_client = OpenWrtSSHClient(
        host=router_host,
        username=router_user,
        password=router_password,
    )
    client = OpenWrtClient(
        host=router_host,
        username=router_user,
        password=router_password,
        verify_ssl=False,
        ssh_client=ssh_client,
    )
    return {
        "router_host": router_host,
        "router_user": router_user,
        "ssh_client": ssh_client,
        "client": client,
    }


def bootstrap_backend():
    env = build_clients()
    client = env["client"]
    ssh_client = env["ssh_client"]

    if not _state["warmed_up"]:
        warmup_model()
        _state["warmed_up"] = True

    capability = probe_router_capabilities(client)
    prereq = build_prereq_audit(capability)

    try:
        real_apply_probe = check_router_real_apply_readiness(ssh_client)
    except Exception as e:
        real_apply_probe = {
            "ok": False,
            "checks": {
                "dnsmasq_nftset_supported": False,
                "dnsmasq_ipset_supported": False,
            },
            "evidence": {},
            "reason": f"SSH readiness probe failed: {e}",
        }

    package_diag = diagnose_dnsmasq_packages(ssh_client)
    remediation_plan = build_dnsmasq_remediation_plan(package_diag)
    feed_diag = diagnose_apk_feeds(ssh_client)
    backend_summary = summarize_backend_status(prereq, real_apply_probe, package_diag, feed_diag)
    dnsmasq_upgrade_plan = build_dnsmasq_full_upgrade_plan(package_diag, feed_diag)
    qos_probe = probe_qos_capabilities(client)
    qos_diag = diagnose_qos_packages(ssh_client)
    qos_fix_plan = build_qos_install_plan(qos_diag)
    qos_install_need = summarize_qos_install_need(qos_probe, qos_diag)

    discovered_devices = merge_into_cache(discover_devices(client))
    available_devices = get_all_available_devices(client)

    snapshot = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "router": {
            "host": env["router_host"],
            "user": env["router_user"],
            "password_set": bool(os.getenv("ROUTER_PASSWORD")),
        },
        "capability": capability,
        "prereq": prereq,
        "real_apply_probe": real_apply_probe,
        "package_diag": package_diag,
        "remediation_plan": remediation_plan,
        "feed_diag": feed_diag,
        "backend_summary": backend_summary,
        "dnsmasq_upgrade_plan": dnsmasq_upgrade_plan,
        "qos_probe": qos_probe,
        "qos_diag": qos_diag,
        "qos_fix_plan": qos_fix_plan,
        "qos_install_need": qos_install_need,
        "discovered_devices": discovered_devices,
        "available_devices": available_devices,
        "supported_apps": list_supported_apps(),
        "supported_aliases": list_supported_aliases(),
        "dry_run_rules": DRY_RUN_RULES,
        "dry_run_packages": DRY_RUN_PACKAGES,
    }
    _state["last_bootstrap"] = snapshot
    safe_log("browser_bootstrap", snapshot)
    return env, snapshot


def summarize_result(validated, matched, app_resolution, gated_exec_spec, apply_result, schedule_apply_result, verify_result, pre_snapshot, post_snapshot, rollback_record):
    return {
        "intent": validated.get("intent"),
        "device": matched,
        "application_resolution": app_resolution,
        "backend_gate": gated_exec_spec.get("backend_gate", {}),
        "apply_result": apply_result,
        "schedule_apply_result": schedule_apply_result,
        "verify_result": verify_result,
        "pre_snapshot": pre_snapshot,
        "post_snapshot": post_snapshot,
        "rollback_record": rollback_record,
        "user_message": build_user_message(apply_result, verify_result),
    }


def build_user_message(apply_result, verify_result):
    if (
        verify_result.get("verified")
        and verify_result.get("live_verified")
        and verify_result.get("schedule_verified") is True
    ):
        return "Live and scheduled QoS policy applied and verified successfully."
    if (
        apply_result.get("applied")
        and verify_result.get("live_verified")
        and verify_result.get("schedule_verified") is False
    ):
        return "Live QoS rule applied and verified, but scheduled automation was not installed."
    if apply_result.get("applied") and verify_result.get("verified"):
        return "QoS rule applied and verified successfully."
    if apply_result.get("applied"):
        return "Live QoS rule applied, but verification did not pass."
    return "Apply did not complete successfully."


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/bootstrap")
def api_bootstrap():
    try:
        _, snapshot = bootstrap_backend()
        return jsonify({"ok": True, "data": snapshot})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.post("/api/plan")
def api_plan():
    payload = request.get_json(silent=True) or {}
    user_prompt = (payload.get("prompt") or "").strip()

    if not user_prompt:
        return jsonify({"ok": False, "error": "Prompt is required."}), 400

    try:
        env, snapshot = bootstrap_backend()
        client = env["client"]

        raw_result = parse_prompt_to_router_json(user_prompt)
        base_normalized = normalize_router_output(raw_result)
        normalized = normalize_qos_intent(base_normalized)
        validated = validate_router_output(normalized)
        validated = enrich_validated_request_for_priority(validated)

        if validated["needs_clarification"]:
            return jsonify({
                "ok": True,
                "mode": "clarification",
                "clarification_question": validated["clarification_question"],
                "validated": validated,
                "bootstrap": snapshot,
            })

        plan = build_execution_plan(validated)
        all_devices = get_all_available_devices(client)
        resolution = resolve_target_device(validated, all_devices)

        if not resolution.get("ok"):
            cached = find_cached_device(validated["target_device"])
            if cached:
                resolution = {
                    "ok": True,
                    "device": cached,
                    "reason": None,
                    "available_devices": resolution.get("available_devices", []),
                    "candidates": [cached],
                    "warning": "Live discovery failed; using cached device identity."
                }

        if not resolution.get("ok"):
            clarification = build_clarification_response(validated, resolution)
            return jsonify({
                "ok": True,
                "mode": "clarification",
                "clarification": clarification,
                "validated": validated,
                "bootstrap": snapshot,
            })

        matched = resolution.get("device")
        final_plan = enrich_plan_with_device(plan, matched)
        app_resolution = None

        if validated.get("intent") == "schedule_priority":
            exec_spec = build_priority_execution_spec(validated, matched)
            gated_exec_spec = apply_qos_backend_readiness_gate(exec_spec, snapshot["qos_probe"])
            app_resolution = resolve_application_signature(
                gated_exec_spec.get("match", {}).get("application")
                or gated_exec_spec.get("match", {}).get("service")
            )
        else:
            exec_spec = build_execution_spec(final_plan)
            gated_exec_spec = apply_backend_readiness_gate(exec_spec, snapshot["prereq"], snapshot["real_apply_probe"])

        unsupported = False
        if validated.get("intent") == "schedule_priority" and not (app_resolution or {}).get("known", False):
            unsupported = True

        response = {
            "ok": True,
            "mode": "preview",
            "prompt": user_prompt,
            "bootstrap": snapshot,
            "raw_result": raw_result,
            "normalized": normalized,
            "validated": validated,
            "plan": plan,
            "resolution": resolution,
            "final_plan": final_plan,
            "exec_spec": exec_spec,
            "gated_exec_spec": gated_exec_spec,
            "app_resolution": app_resolution,
            "unsupported_application": unsupported,
            "supported_apps": list_supported_apps(),
        }
        safe_log("browser_plan_preview", response)
        return jsonify(response)
    except ValidationError as e:
        return jsonify({"ok": False, "error": str(e), "type": "validation"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.post("/api/apply")
def api_apply():
    payload = request.get_json(silent=True) or {}
    user_prompt = (payload.get("prompt") or "").strip()
    approve = bool(payload.get("approve", True))
    apply_live = bool(payload.get("apply_live", False))

    if not user_prompt:
        return jsonify({"ok": False, "error": "Prompt is required."}), 400
    if not approve:
        return jsonify({"ok": True, "cancelled": True, "message": "Cancelled by user."})

    try:
        env, snapshot = bootstrap_backend()
        client = env["client"]
        ssh_client = env["ssh_client"]

        raw_result = parse_prompt_to_router_json(user_prompt)
        base_normalized = normalize_router_output(raw_result)
        normalized = normalize_qos_intent(base_normalized)
        validated = validate_router_output(normalized)
        validated = enrich_validated_request_for_priority(validated)

        if validated["needs_clarification"]:
            return jsonify({
                "ok": False,
                "error": validated["clarification_question"],
                "type": "clarification"
            }), 400

        plan = build_execution_plan(validated)
        devices = merge_into_cache(discover_devices(client))
        all_devices = get_all_available_devices(client)
        resolution = resolve_target_device(validated, all_devices)

        if not resolution.get("ok"):
            cached = find_cached_device(validated["target_device"])
            if cached:
                resolution = {
                    "ok": True,
                    "device": cached,
                    "reason": None,
                    "available_devices": resolution.get("available_devices", []),
                    "candidates": [cached],
                    "warning": "Live discovery failed; using cached device identity."
                }

        if not resolution.get("ok"):
            clarification = build_clarification_response(validated, resolution)
            return jsonify({"ok": False, "error": clarification, "type": "clarification"}), 400

        matched = resolution.get("device")
        final_plan = enrich_plan_with_device(plan, matched)
        app_resolution = None

        if validated.get("intent") == "schedule_priority":
            exec_spec = build_priority_execution_spec(validated, matched)
            gated_exec_spec = apply_qos_backend_readiness_gate(exec_spec, snapshot["qos_probe"])
            app_resolution = resolve_application_signature(
                gated_exec_spec.get("match", {}).get("application")
                or gated_exec_spec.get("match", {}).get("service")
            )
            if not app_resolution.get("known", False):
                return jsonify({
                    "ok": False,
                    "error": "Unsupported app for QoS right now.",
                    "supported_apps": list_supported_apps(),
                    "app_resolution": app_resolution,
                }), 400
        else:
            exec_spec = build_execution_spec(final_plan)
            gated_exec_spec = apply_backend_readiness_gate(exec_spec, snapshot["prereq"], snapshot["real_apply_probe"])

        rules_before = load_rules()
        pre_snapshot = save_snapshot("pre_change", {
            "prompt": user_prompt,
            "validated": validated,
            "plan": plan,
            "final_plan": final_plan,
            "exec_spec": exec_spec,
            "gated_exec_spec": gated_exec_spec,
            "rules_before": rules_before,
            "devices": devices,
            "resolution": resolution,
        })

        ensure_real_apply_allowed(gated_exec_spec, DRY_RUN_RULES)
        rule_backend_gate = gated_exec_spec.get("backend_gate", {})
        rule_real_apply_ready = bool(rule_backend_gate.get("real_apply_ready", False))
        rule_apply_dry_run = not (rule_real_apply_ready and apply_live)

        if validated.get("intent") == "schedule_priority":
            if rule_apply_dry_run:
                apply_result = apply_execution_spec(
                    exec_spec=gated_exec_spec,
                    client=client,
                    dry_run=True,
                    qos_probe=snapshot["qos_probe"],
                )
            else:
                qosify_plan = build_qosify_live_plan(gated_exec_spec, app_resolution)
                apply_result = execute_qosify_live_plan(
                    ssh_client=ssh_client,
                    plan=qosify_plan,
                    dry_run=False,
                )
        else:
            apply_result = apply_execution_spec(
                exec_spec=gated_exec_spec,
                client=client,
                dry_run=rule_apply_dry_run,
                qos_probe=snapshot["qos_probe"],
            )

        schedule_apply_result = {
            "applied": False,
            "plan": None,
            "results": [],
            "failures": [],
            "reason": "Schedule phase skipped."
        }

        if validated.get("intent") == "schedule_priority" and apply_result.get("applied"):
            cron_backend = detect_scheduler_backend(ssh_client)
            schedule_plan = build_runtime_qosify_schedule_plan(apply_result["writer_plan"], cron_backend)
            schedule_apply_result = apply_qosify_schedule_plan(ssh_client, schedule_plan)

        verify_debug_probe = {"skipped": True, "reason": "Not a live QoS flow."}
        if (
            validated.get("intent") == "schedule_priority"
            and apply_result.get("writer_plan", {}).get("remote_path")
        ):
            remote_path = apply_result["writer_plan"]["remote_path"]
            verify_debug_probe = run_ssh_normalized(
                ssh_client,
                f"test -s '{remote_path}'",
                check=False,
            )

        if validated.get("intent") == "schedule_priority":
            verify_result = verify_qosify_result(
                ssh_client,
                apply_result=apply_result,
                schedule_apply_result=schedule_apply_result,
            )
        else:
            verify_result = {
                "verified": apply_result.get("applied", False),
                "live_verified": apply_result.get("applied", False),
                "schedule_verified": None,
                "mode": "non_qos_verification_placeholder",
                "reason": "Non-QoS verification path not routed through qosify verifier."
            }

        rules_after = load_rules()
        post_snapshot = save_snapshot("post_change", {
            "prompt": user_prompt,
            "exec_spec": exec_spec,
            "gated_exec_spec": gated_exec_spec,
            "apply_result": apply_result,
            "verify_result": verify_result,
            "rules_after": rules_after,
        })

        rollback_record = save_rollback_record({
            "prompt": user_prompt,
            "exec_spec": exec_spec,
            "gated_exec_spec": gated_exec_spec,
            "pre_snapshot": pre_snapshot,
            "post_snapshot": post_snapshot,
            "apply_result": apply_result,
            "verify_result": verify_result,
        })

        response = {
            "ok": True,
            "prompt": user_prompt,
            "bootstrap": snapshot,
            "raw_result": raw_result,
            "normalized": normalized,
            "validated": validated,
            "plan": plan,
            "resolution": resolution,
            "final_plan": final_plan,
            "exec_spec": exec_spec,
            "gated_exec_spec": gated_exec_spec,
            "verify_debug_probe": verify_debug_probe,
            "result": summarize_result(
                validated,
                matched,
                app_resolution,
                gated_exec_spec,
                apply_result,
                schedule_apply_result,
                verify_result,
                pre_snapshot,
                post_snapshot,
                rollback_record,
            ),
        }
        safe_log("browser_apply_result", response)
        return jsonify(response)
    except ValidationError as e:
        return jsonify({"ok": False, "error": str(e), "type": "validation"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)