import json
import os
import traceback

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
from dnsmasq_remediation import (
    build_dnsmasq_remediation_plan,
    execute_dnsmasq_remediation_plan,
)
from apply_guard import ensure_real_apply_allowed
from feed_diagnostics import diagnose_apk_feeds
from status_summary import summarize_backend_status
from dnsmasq_installer import (
    build_dnsmasq_full_upgrade_plan,
    execute_dnsmasq_full_upgrade_plan,
)
from verify_openwrt_domain_block import verify_openwrt_domain_block

from priority_intent_support import (
    enrich_validated_request_for_priority,
    build_priority_execution_spec,
)
from qos_capability_probe import probe_qos_capabilities
from qos_package_diagnostics import diagnose_qos_packages
from qos_fix_planner import build_qos_install_plan
from qos_install_flow import should_offer_qos_install, summarize_qos_install_need
from qos_fix_executor import execute_qos_install_plan
from qosify_catalog import resolve_application_signature
from qosify_live_plan import build_qosify_live_plan
from qosify_live_executor import execute_qosify_live_plan
# from qosify_verify import verify_qosify_live_rule
from qosify_schedule_plan import build_qosify_schedule_plan
# from qosify_schedule_executor import execute_qosify_schedule_plan
# from qosify_schedule_verify import verify_qosify_schedule_plan
from intent_normalizer import normalize_qos_intent
# from qosify_schedule_writer import build_qosify_schedule_plan
# from qosify_verify import verify_qosify_rule
from ssh_output_cleaner import normalize_ssh_result
# from schedule_backend import detect_cron_backend, build_qosify_schedule_plan
from verify_qosify import verify_qosify_result
from ssh_result_utils import run_ssh_normalized
from cron_capability import detect_scheduler_backend
from apply_schedule_plan import apply_qosify_schedule_plan
from qosify_schedule_plan import build_qosify_schedule_plan as build_runtime_qosify_schedule_plan
from supported_apps import list_supported_apps, list_supported_aliases





DRY_RUN_RULES = True
DRY_RUN_PACKAGES = False


def pretty(title: str, data):
    print(f"\n=== {title} ===")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data)


def main():
    print("=== STARTING main.py ===")
    print("SCRIPT FILE:", os.path.abspath(__file__))
    print("WORKING DIR :", os.getcwd())
    print("DRY_RUN_RULES:", DRY_RUN_RULES)

    try:
        print("\n=== STEP 0: warming up model ===")
        warmup_model()
        print("Model warmup complete.")

        print("\n=== STEP 1: router connection setup ===")
        router_host = os.getenv("ROUTER_HOST", "192.168.56.2")
        router_user = os.getenv("ROUTER_USER", "root")
        router_password = os.getenv("ROUTER_PASSWORD")

        print("Router host:", router_host)
        print("Router user:", router_user)
        print("Router password set:", bool(router_password))

        print("\n=== STEP 1A: creating OpenWrt SSH client ===")
        ssh_client = OpenWrtSSHClient(
            host=router_host,
            username=router_user,
            password=router_password,
        )
        print("OpenWrt SSH client ready.")

        print("\n=== STEP 1B: creating OpenWrt client ===")
        client = OpenWrtClient(
            host=router_host,
            username=router_user,
            password=router_password,
            verify_ssl=False,
            ssh_client=ssh_client,
        )
        print("OpenWrt client created.")

        print("\n=== STEP 1C: probing router capabilities ===")
        capability = probe_router_capabilities(client)
        pretty("Router capability probe", capability)
        log_event("router_capability_probe", capability)

        print("\n=== STEP 1D: prerequisite audit ===")
        prereq = build_prereq_audit(capability)
        pretty("Prerequisite audit", prereq)
        log_event("prereq", prereq)

        print("\n=== STEP 1E: real-apply readiness probe ===")
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

        pretty("Real apply readiness", real_apply_probe)
        log_event("real_apply_readiness", real_apply_probe)

        print("\n=== STEP 1F: dnsmasq package diagnostics ===")
        package_diag = diagnose_dnsmasq_packages(ssh_client)
        pretty("dnsmasq package diagnostics", package_diag)
        log_event("dnsmasq_package_diagnostics", package_diag)

        print("\n=== STEP 1G: dnsmasq remediation plan ===")
        remediation_plan = build_dnsmasq_remediation_plan(package_diag)
        pretty("dnsmasq remediation plan", remediation_plan)
        log_event("dnsmasq_remediation_plan", remediation_plan)

        if not real_apply_probe.get("ok"):
            run_fix = input("Run dnsmasq remediation plan now? (yes/no): ").strip().lower()
            remediation_result = execute_dnsmasq_remediation_plan(
                ssh_client,
                remediation_plan,
                dry_run=(DRY_RUN_RULES or run_fix != "yes"),
            )
            pretty("dnsmasq remediation result", remediation_result)
            log_event("dnsmasq_remediation_result", remediation_result)

            print("\n=== STEP 1H: re-running package diagnostics ===")
            package_diag = diagnose_dnsmasq_packages(ssh_client)
            pretty("dnsmasq package diagnostics (after remediation)", package_diag)
            log_event("dnsmasq_package_diagnostics_after_remediation", package_diag)

            print("\n=== STEP 1I: re-running real-apply readiness probe ===")
            real_apply_probe = check_router_real_apply_readiness(ssh_client)
            pretty("Real apply readiness (after remediation)", real_apply_probe)
            log_event("real_apply_readiness_after_remediation", real_apply_probe)

        print("\n=== STEP 1J: APK feed diagnostics ===")
        feed_diag = diagnose_apk_feeds(ssh_client)
        pretty("APK feed diagnostics", feed_diag)
        log_event("apk_feed_diagnostics", feed_diag)

        print("\n=== STEP 1K: backend capability summary ===")
        backend_summary = summarize_backend_status(prereq, real_apply_probe, package_diag, feed_diag)
        pretty("Backend capability summary", backend_summary)
        log_event("backend_capability_summary", backend_summary)

        print("\n=== STEP 1L: dnsmasq full upgrade plan ===")
        dnsmasq_upgrade_plan = build_dnsmasq_full_upgrade_plan(package_diag, feed_diag)
        pretty("dnsmasq full upgrade plan", dnsmasq_upgrade_plan)
        log_event("dnsmasq_full_upgrade_plan", dnsmasq_upgrade_plan)

        if not real_apply_probe.get("ok", False) and dnsmasq_upgrade_plan.get("full_available"):
            run_upgrade = input("Run dnsmasq-full upgrade plan now? (yes/no): ").strip().lower()
            upgrade_result = execute_dnsmasq_full_upgrade_plan(
                ssh_client,
                dnsmasq_upgrade_plan,
                dry_run=(DRY_RUN_PACKAGES or run_upgrade != "yes"),
            )
            pretty("dnsmasq full upgrade result", upgrade_result)
            log_event("dnsmasq_full_upgrade_result", upgrade_result)

            if run_upgrade == "yes" and not DRY_RUN_PACKAGES:
                print("\n=== STEP 1M: post-upgrade package diagnostics ===")
                package_diag = diagnose_dnsmasq_packages(ssh_client)
                pretty("dnsmasq package diagnostics (post-upgrade)", package_diag)
                log_event("dnsmasq_package_diagnostics_post_upgrade", package_diag)

                print("\n=== STEP 1N: post-upgrade real-apply readiness ===")
                real_apply_probe = check_router_real_apply_readiness(ssh_client)
                pretty("Real apply readiness (post-upgrade)", real_apply_probe)
                log_event("real_apply_readiness_post_upgrade", real_apply_probe)

                print("\n=== STEP 1O: backend capability summary (post-upgrade) ===")
                backend_summary = summarize_backend_status(prereq, real_apply_probe, package_diag, feed_diag)
                pretty("Backend capability summary (post-upgrade)", backend_summary)
                log_event("backend_capability_summary_post_upgrade", backend_summary)

        print("\n=== STEP 1P: QoS capability probe ===")
        qos_probe = probe_qos_capabilities(client)
        pretty("QoS capability probe", qos_probe)
        log_event("qos_capability_probe", qos_probe)

        print("\n=== STEP 1Q: QoS package diagnostics ===")
        qos_diag = diagnose_qos_packages(ssh_client)
        pretty("QoS package diagnostics", qos_diag)
        log_event("qos_package_diagnostics", qos_diag)

        print("\n=== STEP 1R: QoS install/remediation plan ===")
        qos_fix_plan = build_qos_install_plan(qos_diag)
        pretty("QoS install/remediation plan", qos_fix_plan)
        log_event("qos_install_plan", qos_fix_plan)

        print("\n=== STEP 1S: QoS install decision ===")
        qos_install_need = summarize_qos_install_need(qos_probe, qos_diag)
        pretty("QoS install decision", qos_install_need)
        log_event("qos_install_decision", qos_install_need)

        if should_offer_qos_install(qos_probe, qos_diag):
            user_choice = input("Install QoS backend packages now? (yes/no): ").strip().lower()
            do_install = user_choice == "yes"

            print("\n=== STEP 1T: executing QoS install/remediation plan ===")
            qos_install_result = execute_qos_install_plan(
                ssh_client,
                qos_fix_plan,
                dry_run=not do_install
            )
            pretty("QoS install result", qos_install_result)
            log_event("qos_install_result", qos_install_result)

            if do_install:
                print("\n=== STEP 1U: re-running QoS package diagnostics ===")
                qos_diag = diagnose_qos_packages(ssh_client)
                pretty("QoS package diagnostics (after install)", qos_diag)
                log_event("qos_package_diagnostics_after_install", qos_diag)

                print("\n=== STEP 1V: re-running QoS capability probe ===")
                qos_probe = probe_qos_capabilities(client)
                pretty("QoS capability probe (after install)", qos_probe)
                log_event("qos_capability_probe_after_install", qos_probe)

        while True:
            try:
                print("\n----------------------------------------")
                user_prompt = input("Prompt (or 'exit'): ").strip()

                if user_prompt.lower() in {"exit", "quit"}:
                    print("Exiting.")
                    break

                if not user_prompt:
                    print("Empty prompt, skipping.")
                    continue

                log_event("prompt_received", {"prompt": user_prompt})
                pretty("STEP 2: User prompt", user_prompt)

                print("\n=== STEP 3: calling parse_prompt_to_router_json ===")
                raw_result = parse_prompt_to_router_json(user_prompt)
                pretty("Raw model output", raw_result)
                log_event("raw_model_output", raw_result)

                print("\n=== STEP 4: normalizing output ===")

                base_normalized = normalize_router_output(raw_result)

                print("\n=== Normalized output ===")
                pretty("Normalized output", base_normalized)
                log_event("normalized_output", base_normalized)

                normalized = normalize_qos_intent(base_normalized)

                print("\n=== QoS-intent normalized output ===")
                pretty("QoS-intent normalized output", normalized)
                log_event("qos_intent_normalized_output", normalized)

                print("\n=== STEP 5: validating output ===")
                validated = validate_router_output(normalized)
                pretty("Validated JSON", validated)
                log_event("validated_output", validated)

                validated = enrich_validated_request_for_priority(validated)
                pretty("Priority-enriched validated JSON", validated)
                log_event("priority_enriched_validated_json", validated)

                if validated["needs_clarification"]:
                    pretty("Clarification needed from validator", validated["clarification_question"])
                    log_event("clarification_needed", validated)
                    continue

                print("\n=== STEP 6: building execution plan ===")
                plan = build_execution_plan(validated)
                pretty("Execution plan", plan)
                log_event("execution_plan", plan)

                print("\n=== STEP 7: discovering router devices ===")
                luci_leases = client.get_luci_dhcp_leases()
                ipv4_leases = client.get_dhcp_ipv4_leases()
                ipv6_leases = client.get_dhcp_ipv6_leases()
                odhcpd_leases = client.get_odhcpd_leases()
                odhcpd_hosts = client.get_odhcpd_hosts()
                dns_hosts = client.get_dns_hosts()

                pretty("Raw LuCI DHCP leases", luci_leases)
                pretty("Raw ubus IPv4 leases", ipv4_leases)
                pretty("Raw ubus IPv6 leases", ipv6_leases)
                pretty("Raw odhcpd leases", odhcpd_leases)
                pretty("Raw odhcpd hosts", odhcpd_hosts)
                pretty("Raw dns hosts", dns_hosts)

                devices = discover_devices(client)
                devices = merge_into_cache(devices)
                pretty("Discovered devices", devices)

                all_devices = get_all_available_devices(client)
                pretty("All available devices", all_devices)

                print("\n=== STEP 9: resolving target device ===")
                resolution = resolve_target_device(validated, all_devices)
                pretty("Resolution object", resolution)
                log_event("resolution_object", resolution)

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
                        pretty("Resolution object (cache fallback)", resolution)

                if not resolution.get("ok"):
                    clarification = build_clarification_response(validated, resolution)
                    pretty("Clarification response", clarification)
                    log_event("clarification_needed", clarification)
                    continue

                print("\n=== STEP 10B: enriching final plan with resolved device ===")
                matched = resolution.get("device")
                if not matched:
                    raise RuntimeError(f"Resolver returned ok=True without a device payload: {resolution}")

                pretty("Matched target device", matched)
                log_event("resolved_device", matched)

                final_plan = enrich_plan_with_device(plan, matched)

                print("\n=== STEP 11: building execution spec ===")
                app_resolution = None

                if validated.get("intent") == "schedule_priority":
                    exec_spec = build_priority_execution_spec(validated, matched)
                    pretty("Execution spec", exec_spec)
                    log_event("execution_spec", exec_spec)

                    print("\n=== STEP 11B: applying QoS backend readiness gate ===")
                    gated_exec_spec = apply_qos_backend_readiness_gate(exec_spec, qos_probe)
                    pretty("Gated execution spec", gated_exec_spec)
                    log_event("gated_execution_spec", gated_exec_spec)

                    print("\n=== STEP 11C: resolving application signature ===")
                    app_resolution = resolve_application_signature(
                        gated_exec_spec.get("match", {}).get("application")
                        or gated_exec_spec.get("match", {}).get("service")
                    )
                    pretty("Resolved application signature", app_resolution)
                    log_event("resolved_application_signature", app_resolution)
                    if not app_resolution.get("known", False):
                        supported = list_supported_apps()
                        print("\n=== STEP 11D: unsupported application ===")
                        print("Unsupported app for QoS right now.")
                        pretty("Supported QoS apps", supported)
                        log_event("unsupported_application", {
                            "requested": gated_exec_spec.get("match", {}).get("application")
                                or gated_exec_spec.get("match", {}).get("service"),
                            "resolved": app_resolution,
                            "supported_apps": supported,
                        })
                        continue

                else:
                    exec_spec = build_execution_spec(final_plan)
                    pretty("Execution spec", exec_spec)
                    log_event("execution_spec", exec_spec)

                    print("\n=== STEP 11B: applying backend readiness gate ===")
                    gated_exec_spec = apply_backend_readiness_gate(exec_spec, prereq, real_apply_probe)
                    pretty("Gated execution spec", gated_exec_spec)
                    log_event("gated_execution_spec", gated_exec_spec)

                print("\n=== STEP 12: approval gate ===")
                confirm = input("Approve this plan? (yes/no): ").strip().lower()
                approved = confirm in {"yes", "y"}
                print("Approval input:", confirm)
                log_event("approval_response", {"approved": approved})

                if not approved:
                    print("Cancelled by user.")
                    continue

                print("\n=== STEP 13: creating pre-change snapshot ===")
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
                pretty("Pre-change snapshot", pre_snapshot)
                log_event("pre_change_snapshot", pre_snapshot)

                ensure_real_apply_allowed(gated_exec_spec, DRY_RUN_RULES)

                rule_backend_gate = gated_exec_spec.get("backend_gate", {})
                rule_real_apply_ready = bool(rule_backend_gate.get("real_apply_ready", False))

                print("\n=== STEP 14: applying execution spec ===")
                run_live_apply = "no"
                if rule_real_apply_ready:
                    run_live_apply = input("Backend is ready. Apply rule live now? (yes/no): ").strip().lower()

                rule_apply_dry_run = not (rule_real_apply_ready and run_live_apply == "yes")

                if validated.get("intent") == "schedule_priority":
                    if rule_apply_dry_run:
                        apply_result = apply_execution_spec(
                            exec_spec=gated_exec_spec,
                            client=client,
                            dry_run=True,
                            qos_probe=qos_probe,
                        )
                    else:
                        if not app_resolution or not app_resolution.get("known", False):
                            apply_result = {
                                "applied": False,
                                "mode": "qosify_live_apply_refused",
                                "dry_run": False,
                                "reason": "Unknown application signature; refusing live QoS apply."
                            }
                        else:
                            qosify_plan = build_qosify_live_plan(gated_exec_spec, app_resolution)
                            pretty("QoSify live plan", qosify_plan)
                            log_event("qosify_live_plan", qosify_plan)

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
                        qos_probe=qos_probe,
                    )

                pretty("Apply result", apply_result)
                log_event("apply_result", apply_result)
                print("\n=== STEP 14B: applying schedule plan ===")
                schedule_apply_result = {
                    "applied": False,
                    "plan": None,
                    "results": [],
                    "failures": [],
                    "reason": "Schedule phase skipped."
                }

                if validated.get("intent") == "schedule_priority" and apply_result.get("applied"):
                    cron_backend = detect_scheduler_backend(ssh_client)
                    pretty("Detected cron backend", cron_backend)
                    log_event("detected_cron_backend", cron_backend)

                    schedule_plan = build_runtime_qosify_schedule_plan(apply_result["writer_plan"], cron_backend)
                    pretty("QoSify schedule plan", schedule_plan)
                    log_event("qosify_schedule_plan", schedule_plan)

                    schedule_apply_result = apply_qosify_schedule_plan(ssh_client, schedule_plan)
                    pretty("Schedule apply result", schedule_apply_result)
                    log_event("schedule_apply_result", schedule_apply_result)
                else:
                    pretty("Schedule apply result", schedule_apply_result)
                    log_event("schedule_apply_result", schedule_apply_result)
                print("\n=== VERIFY DEBUG PROBE ===")
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

                pretty("Verify debug probe", verify_debug_probe)
                log_event("verify_debug_probe", verify_debug_probe)
                print("\n=== STEP 15: verifying applied rule ===")
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
                pretty("Verify result", verify_result)
                log_event("verify_result", verify_result)

                print("\n=== STEP 16: creating post-change snapshot ===")
                rules_after = load_rules()
                post_snapshot = save_snapshot("post_change", {
                    "prompt": user_prompt,
                    "exec_spec": exec_spec,
                    "gated_exec_spec": gated_exec_spec,
                    "apply_result": apply_result,
                    "verify_result": verify_result,
                    "rules_after": rules_after,
                })
                pretty("Post-change snapshot", post_snapshot)
                log_event("post_change_snapshot", post_snapshot)

                print("\n=== STEP 17: saving rollback metadata ===")
                rollback_record = save_rollback_record({
                    "prompt": user_prompt,
                    "exec_spec": exec_spec,
                    "gated_exec_spec": gated_exec_spec,
                    "pre_snapshot": pre_snapshot,
                    "post_snapshot": post_snapshot,
                    "apply_result": apply_result,
                    "verify_result": verify_result,
                })
                pretty("Rollback metadata", rollback_record)
                log_event("rollback_record", rollback_record)

                print("\n=== STEP 18: done ===")

                if (
                    verify_result.get("verified")
                    and verify_result.get("live_verified")
                    and verify_result.get("schedule_verified") is True
                ):
                    print("Live and scheduled QoS policy applied and verified successfully.")
                elif (
                    apply_result.get("applied")
                    and verify_result.get("live_verified")
                    and verify_result.get("schedule_verified") is False
                ):
                    print("Live QoS rule applied and verified, but scheduled automation was not installed.")
                elif apply_result.get("applied") and verify_result.get("verified"):
                    print("QoS rule applied and verified successfully.")
                elif apply_result.get("applied"):
                    print("Live QoS rule applied, but verification did not pass.")
                else:
                    print("Apply did not complete successfully.")

            except ValidationError as e:
                print("\n=== VALIDATION ERROR ===")
                print(str(e))
                log_event("validation_failed", {"error": str(e)})
                continue

            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                break

            except Exception as e:
                print("\n=== LOOP RUNTIME ERROR ===")
                print("Error:", str(e))
                traceback.print_exc()
                log_event("runtime_error", {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                continue

    except Exception as e:
        print("\n=== FATAL STARTUP ERROR ===")
        print("Error:", str(e))
        traceback.print_exc()


if __name__ == "__main__":
    main()