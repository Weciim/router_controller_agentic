from datetime import datetime, timezone


def _section_name(res):
    if isinstance(res, dict) and "section" in res:
        return res["section"]
    if isinstance(res, str):
        return res
    raise RuntimeError(f"Unexpected UCI add response: {res}")


def _fail_result(plan, results, reason):
    return {
        "applied": False,
        "dry_run": False,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "results": results,
        "reason": reason,
    }


def execute_openwrt_writer_plan(client, plan: dict, dry_run: bool = True) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "applied_at": timestamp,
            "plan": plan,
            "results": [],
            "reason": "Dry run only. No changes were applied.",
        }

    results = []

    try:
        nftset_v4 = plan["nftset_v4"]
        nftset_v6 = plan["nftset_v6"]
        dhcp_section_name = plan["dhcp_nftset_section"]
        domains = plan.get("domains", [])
        src_ip = plan["src_ip"]
        family = plan["family"]
        hostname = plan["hostname"]
        start_time = plan.get("start_time")
        end_time = plan.get("end_time")
        weekdays = plan.get("weekdays", "Mon Tue Wed Thu Fri")

        fw_nft4 = _section_name(client.uci_add("firewall", "nftset"))
        results.append({"step": "uci_add firewall nftset v4", "section": fw_nft4})

        client.uci_set("firewall", fw_nft4, {
            "name": nftset_v4,
            "family": "ipv4",
            "timeout": "180",
            "match": "dest_ip",
            "enabled": "1",
        })
        results.append({"step": "uci_set firewall nftset v4", "ok": True})

        fw_nft6 = _section_name(client.uci_add("firewall", "nftset"))
        results.append({"step": "uci_add firewall nftset v6", "section": fw_nft6})

        client.uci_set("firewall", fw_nft6, {
            "name": nftset_v6,
            "family": "ipv6",
            "timeout": "180",
            "match": "dest_ip",
            "enabled": "1",
        })
        results.append({"step": "uci_set firewall nftset v6", "ok": True})

        dhcp_sec = _section_name(client.uci_add("dhcp", "nftset", name=dhcp_section_name))
        results.append({"step": "uci_add dhcp nftset", "section": dhcp_sec})

        client.uci_set("dhcp", dhcp_sec, {
            "name": [nftset_v4, nftset_v6],
            "table": "fw4",
            "domain": [f"/{d}/" for d in domains],
        })
        results.append({"step": "uci_set dhcp nftset", "ok": True})

        fw_rule = _section_name(client.uci_add("firewall", "rule"))
        results.append({"step": "uci_add firewall rule", "section": fw_rule})

        client.uci_set("firewall", fw_rule, {
            "name": f"llm_block_{hostname.lower().replace(' ', '_')}_{'d6' if family == 'ipv6' else 'd4'}",
            "src": "lan",
            "src_ip": src_ip,
            "dest": "wan",
            "family": family,
            "ipset": f"{nftset_v6 if family == 'ipv6' else nftset_v4} dest",
            "proto": "all",
            "target": "REJECT",
            "start_time": start_time,
            "stop_time": end_time,
            "weekdays": weekdays,
        })
        results.append({"step": "uci_set firewall rule", "ok": True})

        client.uci_commit("dhcp")
        results.append({"step": "uci_commit dhcp", "ok": True})

        client.uci_commit("firewall")
        results.append({"step": "uci_commit firewall", "ok": True})

        dnsmasq_restart = client.run("/etc/init.d/dnsmasq restart", check=False, prefer_ssh=True)
        results.append({"step": "restart dnsmasq", "ok": dnsmasq_restart.get("ok", False), "result": dnsmasq_restart})

        firewall_restart = client.run("/etc/init.d/firewall restart", check=False, prefer_ssh=True)
        results.append({"step": "restart firewall", "ok": firewall_restart.get("ok", False), "result": firewall_restart})

        return {
            "applied": True,
            "dry_run": False,
            "applied_at": timestamp,
            "plan": plan,
            "results": results,
            "reason": None,
        }

    except Exception as e:
        return _fail_result(plan, results, str(e))