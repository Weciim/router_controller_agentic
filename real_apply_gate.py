from capability_checks import dnsmasq_capability_summary


def check_router_real_apply_readiness(ssh_client) -> dict:
    dnsmasq_help = ssh_client.run("dnsmasq -v 2>&1 || dnsmasq --help 2>&1", check=False)
    summary = dnsmasq_capability_summary(dnsmasq_help.get("stdout", "") + "\n" + dnsmasq_help.get("stderr", ""))

    return {
        "ok": summary["ready_for_real_domain_apply"],
        "checks": {
            "dnsmasq_nftset_supported": summary["supports_nftset"],
            "dnsmasq_ipset_supported": summary["supports_ipset"],
        },
        "evidence": summary,
        "reason": None if summary["ready_for_real_domain_apply"] else (
            "dnsmasq does not appear to support nftset on this router build."
        ),
    }