
def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {"__error__": str(e)}


def _has_error(value) -> bool:
    return isinstance(value, dict) and "__error__" in value


def _stringify(value) -> str:
    if value is None:
        return ""
    return str(value)


def probe_router_capabilities(client) -> dict:
    board = _safe_call(client.get_board_info)

    firewall_cfg = _safe_call(client.uci_get, "firewall")
    dhcp_cfg = _safe_call(client.uci_get, "dhcp")
    network_cfg = _safe_call(client.uci_get, "network")
    firewall_changes = _safe_call(client.uci_changes, "firewall")
    dhcp_changes = _safe_call(client.uci_changes, "dhcp")

    firewall_text = _stringify(firewall_cfg).lower()
    dhcp_text = _stringify(dhcp_cfg).lower()

    has_firewall_uci = not _has_error(firewall_cfg)
    has_dhcp_uci = not _has_error(dhcp_cfg)

    has_fw4_hint = any(x in firewall_text for x in ["rule", "zone", "forwarding", "defaults"])
    has_ipset_or_nftset_hint = any(x in firewall_text + dhcp_text for x in ["ipset", "nftset"])
    has_dnsmasq_hint = any(x in dhcp_text for x in ["dnsmasq", "domain", "server", "rebind"])

    release = board.get("release", {}) if isinstance(board, dict) else {}

    readiness = {
        "has_firewall_uci": has_firewall_uci,
        "has_dhcp_uci": has_dhcp_uci,
        "has_fw4_hint": has_fw4_hint,
        "has_ipset_or_nftset_hint": has_ipset_or_nftset_hint,
        "has_dnsmasq_hint": has_dnsmasq_hint,
        "can_confidently_do_domain_blocking_next": bool(has_firewall_uci and has_dhcp_uci),
    }

    return {
        "board": board,
        "raw": {
            "firewall_cfg": firewall_cfg,
            "dhcp_cfg": dhcp_cfg,
            "network_cfg": network_cfg,
            "firewall_changes": firewall_changes,
            "dhcp_changes": dhcp_changes,
        },
        "readiness": readiness,
        "release_summary": {
            "distribution": release.get("distribution"),
            "version": release.get("version"),
            "target": release.get("target"),
            "description": release.get("description"),
        },
    }