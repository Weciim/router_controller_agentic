def _safe_uci_get(client, config: str):
    try:
        return client.uci_get(config=config)
    except Exception as e:
        return {"__error__": str(e)}


def _flatten_text(obj) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return str(obj)


def verify_openwrt_domain_block(client, writer_plan: dict) -> dict:
    nftset_v4 = writer_plan.get("nftset_v4")
    nftset_v6 = writer_plan.get("nftset_v6")
    dhcp_section = writer_plan.get("dhcp_nftset_section")
    src_ip = writer_plan.get("src_ip")
    family = writer_plan.get("family")

    firewall_cfg = _safe_uci_get(client, "firewall")
    dhcp_cfg = _safe_uci_get(client, "dhcp")

    firewall_text = _flatten_text(firewall_cfg)
    dhcp_text = _flatten_text(dhcp_cfg)

    checks = {
        "firewall_rpc_ok": "__error__" not in firewall_text,
        "dhcp_rpc_ok": "__error__" not in dhcp_text,
        "firewall_contains_v4_set": nftset_v4 in firewall_text if nftset_v4 else False,
        "firewall_contains_v6_set": nftset_v6 in firewall_text if nftset_v6 else False,
        "dhcp_contains_domain_mapping": any(
            token in dhcp_text for token in [dhcp_section or "", nftset_v4 or "", nftset_v6 or ""]
        ),
        "firewall_contains_src_ip": src_ip in firewall_text if src_ip else False,
        "family_matches_expected": (
            ("'family': 'ipv6'" in firewall_text or '"family": "ipv6"' in firewall_text or "family': 'ipv6" in firewall_text)
            if family == "ipv6"
            else ("'family': 'ipv4'" in firewall_text or '"family": "ipv4"' in firewall_text or "family': 'ipv4" in firewall_text)
            if family == "ipv4"
            else False
        ),
    }

    if family == "ipv6":
        verified = (
            checks["firewall_rpc_ok"]
            and checks["dhcp_rpc_ok"]
            and checks["firewall_contains_v6_set"]
            and checks["dhcp_contains_domain_mapping"]
            and checks["firewall_contains_src_ip"]
        )
    else:
        verified = (
            checks["firewall_rpc_ok"]
            and checks["dhcp_rpc_ok"]
            and checks["firewall_contains_v4_set"]
            and checks["dhcp_contains_domain_mapping"]
            and checks["firewall_contains_src_ip"]
        )

    return {
        "verified": verified,
        "checks": checks,
        "evidence": {
            "firewall_cfg": firewall_cfg,
            "dhcp_cfg": dhcp_cfg,
        },
    }