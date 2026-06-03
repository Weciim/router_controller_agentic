from datetime import datetime
import ipaddress


def _utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _normalize_ip(ip_value: str):
    if not ip_value:
        raise ValueError("Target IP is required")

    raw = ip_value.strip()
    if "/" in raw:
        addr = raw.split("/", 1)[0]
    else:
        addr = raw

    parsed = ipaddress.ip_address(addr)
    family = "ipv6" if parsed.version == 6 else "ipv4"
    return addr, family


def _normalize_weekdays(days: list[str] | None) -> str | None:
    if not days:
        return None

    day_map = {
        "weekdays": "Mon Tue Wed Thu Fri",
        "weekends": "Sat Sun",
        "monday": "Mon",
        "tuesday": "Tue",
        "wednesday": "Wed",
        "thursday": "Thu",
        "friday": "Fri",
        "saturday": "Sat",
        "sunday": "Sun",
        "mon": "Mon",
        "tue": "Tue",
        "wed": "Wed",
        "thu": "Thu",
        "fri": "Fri",
        "sat": "Sat",
        "sun": "Sun",
    }

    normalized = []
    for d in days:
        if not d:
            continue
        key = d.strip().lower()
        mapped = day_map.get(key)
        if mapped:
            normalized.extend(mapped.split())

    if not normalized:
        return None

    ordered = []
    seen = set()
    for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        if d in normalized and d not in seen:
            ordered.append(d)
            seen.add(d)

    return " ".join(ordered) if ordered else None


def build_scheduled_device_block_commands(exec_spec: dict) -> dict:
    target = exec_spec["target"]
    schedule = exec_spec["schedule"]

    hostname = target.get("hostname") or "unknown-device"
    raw_ip = target.get("ip")
    start_time = schedule.get("start_time")
    end_time = schedule.get("end_time")
    days = schedule.get("days") or []

    if not raw_ip:
        raise ValueError("Resolved device IP is required for firewall block")
    if not start_time or not end_time:
        raise ValueError("start_time and end_time are required")

    src_ip, family = _normalize_ip(raw_ip)
    weekdays = _normalize_weekdays(days)

    safe_hostname = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in hostname)
    rule_name = f"llm_block_{safe_hostname}_{start_time}_{end_time}".replace(":", "_")

    commands = [
        "uci add firewall rule",
        f"uci set firewall.@rule[-1].name='{rule_name}'",
        "uci set firewall.@rule[-1].src='lan'",
        f"uci set firewall.@rule[-1].src_ip='{src_ip}'",
        f"uci set firewall.@rule[-1].family='{family}'",
        "uci set firewall.@rule[-1].dest='wan'",
        "uci set firewall.@rule[-1].proto='all'",
        "uci set firewall.@rule[-1].target='REJECT'",
        f"uci set firewall.@rule[-1].start_time='{start_time}'",
        f"uci set firewall.@rule[-1].stop_time='{end_time}'",
    ]

    if weekdays:
        commands.append(f"uci set firewall.@rule[-1].weekdays='{weekdays}'")

    commands.extend([
        "uci commit firewall",
        "/etc/init.d/firewall reload",
        f"uci show firewall | grep \"{rule_name}\"",
    ])

    return {
        "mode": "scheduled_device_block_prototype",
        "rule_name": rule_name,
        "hostname": hostname,
        "src_ip": src_ip,
        "family": family,
        "weekdays": weekdays,
        "start_time": start_time,
        "end_time": end_time,
        "commands": commands,
    }


def apply_scheduled_device_block(client, exec_spec: dict, dry_run: bool = False) -> dict:
    plan = build_scheduled_device_block_commands(exec_spec)

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "applied_at": _utc_now(),
            "plan": plan,
        }

    backup_firewall = client.run_shell("uci export firewall")
    backup_dhcp = client.run_shell("uci export dhcp")

    command_outputs = []
    for cmd in plan["commands"]:
        out = client.run_shell(cmd)
        command_outputs.append({
            "command": cmd,
            "output": out,
        })

    verification_output = command_outputs[-1]["output"] if command_outputs else ""

    return {
        "applied": True,
        "dry_run": False,
        "applied_at": _utc_now(),
        "plan": plan,
        "backup": {
            "firewall_uci": backup_firewall,
            "dhcp_uci": backup_dhcp,
        },
        "command_outputs": command_outputs,
        "verification": verification_output,
    }