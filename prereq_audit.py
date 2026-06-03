
def build_prereq_audit(capability: dict) -> dict:
    readiness = capability.get("readiness", {}) if isinstance(capability, dict) else {}
    release = capability.get("release_summary", {}) if isinstance(capability, dict) else {}
    board = capability.get("board", {}) if isinstance(capability, dict) else {}

    checks = {
        "board_info_available": bool(board),
        "firewall_uci_available": bool(readiness.get("has_firewall_uci")),
        "dhcp_uci_available": bool(readiness.get("has_dhcp_uci")),
        "fw4_hint_present": bool(readiness.get("has_fw4_hint")),
        "dnsmasq_hint_present": bool(readiness.get("has_dnsmasq_hint")),
        "ipset_or_nftset_hint_present": bool(readiness.get("has_ipset_or_nftset_hint")),
        "true_domain_backend_probe_ready": bool(readiness.get("can_confidently_do_domain_blocking_next")),
    }

    blockers = []
    warnings = []
    recommendations = []

    if not checks["board_info_available"]:
        blockers.append("Router board information is unavailable.")
    if not checks["firewall_uci_available"]:
        blockers.append("UCI firewall configuration is not accessible through RPC.")
    if not checks["dhcp_uci_available"]:
        blockers.append("UCI DHCP configuration is not accessible through RPC.")
    if not checks["fw4_hint_present"]:
        blockers.append("No firewall4-compatible configuration hint was detected.")

    if not checks["dnsmasq_hint_present"]:
        warnings.append("No dnsmasq hint detected in DHCP config.")
    if not checks["ipset_or_nftset_hint_present"]:
        warnings.append("No existing ipset/nftset config found yet; the writer may need to create it.")

    ready = (
        checks["board_info_available"]
        and checks["firewall_uci_available"]
        and checks["dhcp_uci_available"]
        and checks["fw4_hint_present"]
        and checks["true_domain_backend_probe_ready"]
    )

    if ready:
        recommendations.append("Router config is accessible; proceed to a true UCI-backed domain-block dry-run writer.")
    else:
        recommendations.append("Stay in prototype mode until UCI config access and backend readiness are confirmed.")

    return {
        "summary": {
            "router_model": board.get("model"),
            "router_target": release.get("target"),
            "router_version": release.get("description"),
            "ready_for_true_domain_backend": ready,
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "recommendations": recommendations,
    }