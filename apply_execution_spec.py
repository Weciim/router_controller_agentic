from openwrt_writer_executor import execute_openwrt_writer_plan
from rules_store import store_rule_record
from qos_plan_builder import build_qos_priority_plan


def build_openwrt_writer_plan(exec_spec: dict) -> dict:
    target = exec_spec.get("target", {})
    match = exec_spec.get("match", {})
    schedule = exec_spec.get("schedule", {})
    backend_gate = exec_spec.get("backend_gate", {})

    hostname = target.get("hostname")
    src_ip = target.get("ip")
    domains = match.get("domains", [])

    is_ipv6 = ":" in (src_ip or "")
    family = "ipv6" if is_ipv6 else "ipv4"

    host_slug = (hostname or "device").lower().replace(" ", "_")
    nftset_v4 = f"llm_{host_slug}_d4"
    nftset_v6 = f"llm_{host_slug}_d6"
    dhcp_nftset_section = f"llm_{host_slug}_dnsset"

    commands = [
        "uci add firewall nftset",
        f"uci set firewall.@nftset[-1].name='{nftset_v4}'",
        "uci set firewall.@nftset[-1].table='fw4'",
        "uci set firewall.@nftset[-1].family='ipv4'",
        "uci set firewall.@nftset[-1].match='dest_ip'",
        "uci set firewall.@nftset[-1].enabled='1'",
        "uci add firewall nftset",
        f"uci set firewall.@nftset[-1].name='{nftset_v6}'",
        "uci set firewall.@nftset[-1].table='fw4'",
        "uci set firewall.@nftset[-1].family='ipv6'",
        "uci set firewall.@nftset[-1].match='dest_ip'",
        "uci set firewall.@nftset[-1].enabled='1'",
        "uci add dhcp nftset",
        f"uci set dhcp.@nftset[-1].name='{dhcp_nftset_section}'",
        f"uci add_list dhcp.@nftset[-1].name='{nftset_v4}'",
        f"uci add_list dhcp.@nftset[-1].name='{nftset_v6}'",
        "uci set dhcp.@nftset[-1].table='fw4'",
    ]

    for domain in domains:
        commands.append(f"uci add_list dhcp.@nftset[-1].domain='/{domain}/'")

    commands.extend([
        "uci add firewall rule",
        f"uci set firewall.@rule[-1].name='llm_block_{host_slug}_{'d6' if is_ipv6 else 'd4'}'",
        "uci set firewall.@rule[-1].src='lan'",
        f"uci set firewall.@rule[-1].src_ip='{src_ip}'",
        "uci set firewall.@rule[-1].dest='wan'",
        f"uci set firewall.@rule[-1].family='{family}'",
        f"uci set firewall.@rule[-1].ipset='{nftset_v6 if is_ipv6 else nftset_v4} dest'",
        "uci set firewall.@rule[-1].proto='all'",
        "uci set firewall.@rule[-1].target='REJECT'",
        f"uci set firewall.@rule[-1].start_time='{schedule.get('start_time')}'",
        f"uci set firewall.@rule[-1].stop_time='{schedule.get('end_time')}'",
        "uci set firewall.@rule[-1].weekdays='Mon Tue Wed Thu Fri'",
        "uci commit dhcp",
        "uci commit firewall",
        "/etc/init.d/dnsmasq restart",
        "/etc/init.d/firewall restart",
    ])

    return {
        "mode": "scheduled_domain_block_fw4_dnsmasq",
        "hostname": hostname,
        "src_ip": src_ip,
        "family": family,
        "domains": domains,
        "start_time": schedule.get("start_time"),
        "end_time": schedule.get("end_time"),
        "weekdays": "Mon Tue Wed Thu Fri",
        "nftset_v4": nftset_v4,
        "nftset_v6": nftset_v6,
        "dhcp_nftset_section": dhcp_nftset_section,
        "commands": commands,
        "capability_status": {
            "dry_run_valid": True,
            "real_apply_ready": bool(backend_gate.get("real_apply_ready", False)),
            "reason": (
                "Ready for live apply."
                if backend_gate.get("real_apply_ready", False)
                else backend_gate.get("warning", "Plan preview generated successfully.")
            ),
        },
    }


def apply_execution_spec(exec_spec: dict, client, dry_run: bool = True) -> dict:
    backend_gate = exec_spec.get("backend_gate", {})
    writer_plan = build_openwrt_writer_plan(exec_spec)

    if dry_run:
        writer_result = execute_openwrt_writer_plan(client, writer_plan, dry_run=True)
        stored_rule = store_rule_record(exec_spec, writer_plan, mode="dry_run")
        return {
            "applied": False,
            "mode": "openwrt_dry_run_and_store",
            "dry_run": True,
            "operation": exec_spec.get("operation"),
            "rule_type": exec_spec.get("rule_type"),
            "backend_gate": backend_gate,
            "rule": stored_rule,
            "writer_result": writer_result,
        }

    if not backend_gate.get("real_apply_ready", False):
        return {
            "applied": False,
            "mode": "blocked_by_backend_gate",
            "dry_run": False,
            "operation": exec_spec.get("operation"),
            "rule_type": exec_spec.get("rule_type"),
            "reason": backend_gate.get("warning") or "Real apply is blocked.",
            "backend_gate": backend_gate,
        }

    writer_result = execute_openwrt_writer_plan(client, writer_plan, dry_run=False)
    stored_rule = store_rule_record(exec_spec, writer_plan, mode="apply")

    return {
        "applied": bool(writer_result.get("applied", False)),
        "mode": "openwrt_live_apply",
        "dry_run": False,
        "operation": exec_spec.get("operation"),
        "rule_type": exec_spec.get("rule_type"),
        "reason": writer_result.get("reason"),
        "backend_gate": backend_gate,
        "rule": stored_rule,
        "writer_result": writer_result,
    }
def apply_execution_spec(exec_spec: dict, client, dry_run: bool = True, qos_probe: dict | None = None) -> dict:
    backend_gate = exec_spec.get("backend_gate", {})
    rule_type = exec_spec.get("rule_type")

    if rule_type == "scheduled_app_priority":
        writer_plan = build_qos_priority_plan(exec_spec, qos_probe=qos_probe)

        if dry_run:
            return {
                "applied": False,
                "mode": "qos_priority_dry_run",
                "dry_run": True,
                "operation": exec_spec.get("operation"),
                "rule_type": rule_type,
                "backend_gate": backend_gate,
                "writer_plan": writer_plan,
                "reason": "QoS dry-run generated successfully.",
            }

        if not backend_gate.get("real_apply_ready", False):
            return {
                "applied": False,
                "mode": "blocked_by_backend_gate",
                "dry_run": False,
                "operation": exec_spec.get("operation"),
                "rule_type": rule_type,
                "reason": backend_gate.get("warning") or "Real apply is blocked.",
                "backend_gate": backend_gate,
                "writer_plan": writer_plan,
            }

        return {
            "applied": False,
            "mode": "qos_priority_live_not_implemented_yet",
            "dry_run": False,
            "operation": exec_spec.get("operation"),
            "rule_type": rule_type,
            "backend_gate": backend_gate,
            "writer_plan": writer_plan,
            "reason": "QoS live apply backend is the next implementation step.",
        }