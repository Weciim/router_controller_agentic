def summarize_backend_status(prereq_audit: dict, real_apply_probe: dict, package_diag: dict, feed_diag: dict | None = None) -> dict:
    checks = (prereq_audit or {}).get("checks", {})
    pkg_checks = (package_diag or {}).get("checks", {})
    feed_checks = (feed_diag or {}).get("checks", {}) if feed_diag else {}

    config_backend_ready = bool(checks.get("true_domain_backend_probe_ready", False))
    real_apply_ready = bool((real_apply_probe or {}).get("ok", False))

    blockers = []

    if not checks.get("firewall_uci_available", False):
        blockers.append("Firewall UCI is not accessible.")
    if not checks.get("dhcp_uci_available", False):
        blockers.append("DHCP UCI is not accessible.")
    if not pkg_checks.get("dnsmasq_nftset_detected", False):
        blockers.append("Installed dnsmasq lacks nftset support.")

    dnsmasq_full_available = bool(pkg_checks.get("dnsmasq_full_available", False)) or bool(feed_checks.get("dnsmasq_full_search_has_hits", False))
    if not dnsmasq_full_available:
        blockers.append("Feeds do not currently expose dnsmasq-full.")

    if real_apply_ready:
        next_step = "ready_for_real_apply"
    elif dnsmasq_full_available:
        next_step = "upgrade_to_dnsmasq_full"
    else:
        next_step = "inspect_feeds_or_change_backend"

    return {
        "config_backend_ready": config_backend_ready,
        "real_apply_ready": real_apply_ready,
        "dry_run_only": not real_apply_ready,
        "blockers": blockers,
        "next_step": next_step,
    }