from copy import deepcopy


def _days_to_openwrt_weekdays(days):
    if not days:
        return None

    normalized = [str(d).strip().lower() for d in days]

    if "weekdays" in normalized:
        return "Mon Tue Wed Thu Fri"
    if "weekends" in normalized:
        return "Sat Sun"

    mapping = {
        "mon": "Mon", "monday": "Mon",
        "tue": "Tue", "tuesday": "Tue",
        "wed": "Wed", "wednesday": "Wed",
        "thu": "Thu", "thursday": "Thu",
        "fri": "Fri", "friday": "Fri",
        "sat": "Sat", "saturday": "Sat",
        "sun": "Sun", "sunday": "Sun",
    }

    result = []
    for d in normalized:
        if d in mapping:
            result.append(mapping[d])

    return " ".join(dict.fromkeys(result)) if result else None


def _slug(value: str) -> str:
    safe = []
    for ch in (value or ""):
        safe.append(ch.lower() if ch.isalnum() else "_")
    return "".join(safe).strip("_") or "device"


def _family_from_ip(ip):
    if not ip:
        return None
    return "ipv6" if ":" in ip else "ipv4"


def build_scheduled_domain_block_plan(exec_spec: dict, client=None) -> dict:
    target = exec_spec.get("target", {})
    match = exec_spec.get("match", {})
    schedule = exec_spec.get("schedule", {})

    hostname = target.get("hostname") or "unknown-device"
    src_ip = target.get("ip")
    family = _family_from_ip(src_ip)
    domains = match.get("domains") or []

    if not src_ip:
        raise ValueError("Resolved target device has no IP address.")
    if not domains:
        raise ValueError("No domains were provided for scheduled_domain_block.")

    start_time = schedule.get("start_time")
    end_time = schedule.get("end_time")
    weekdays = _days_to_openwrt_weekdays(schedule.get("days"))
    base = _slug(hostname)

    nft4_name = f"llm_{base}_d4"
    nft6_name = f"llm_{base}_d6"
    dhcp_nft_name = f"llm_{base}_dnsset"
    rule4_name = f"llm_block_{base}_d4"
    rule6_name = f"llm_block_{base}_d6"

    commands = [
        "uci add firewall nftset",
        f"uci set firewall.@nftset[-1].name='{nft4_name}'",
        "uci set firewall.@nftset[-1].table='fw4'",
        "uci set firewall.@nftset[-1].family='ipv4'",
        "uci set firewall.@nftset[-1].match='dest_ip'",
        "uci set firewall.@nftset[-1].enabled='1'",

        "uci add firewall nftset",
        f"uci set firewall.@nftset[-1].name='{nft6_name}'",
        "uci set firewall.@nftset[-1].table='fw4'",
        "uci set firewall.@nftset[-1].family='ipv6'",
        "uci set firewall.@nftset[-1].match='dest_ip'",
        "uci set firewall.@nftset[-1].enabled='1'",

        "uci add dhcp nftset",
        f"uci set dhcp.@nftset[-1].name='{dhcp_nft_name}'",
        f"uci add_list dhcp.@nftset[-1].name='{nft4_name}'",
        f"uci add_list dhcp.@nftset[-1].name='{nft6_name}'",
        "uci set dhcp.@nftset[-1].table='fw4'",
    ]

    for domain in domains:
        commands.append(f"uci add_list dhcp.@nftset[-1].domain='/{domain}/'")

    if family == "ipv4":
        commands += [
            "uci add firewall rule",
            f"uci set firewall.@rule[-1].name='{rule4_name}'",
            "uci set firewall.@rule[-1].src='lan'",
            f"uci set firewall.@rule[-1].src_ip='{src_ip}'",
            "uci set firewall.@rule[-1].dest='wan'",
            "uci set firewall.@rule[-1].family='ipv4'",
            f"uci set firewall.@rule[-1].ipset='{nft4_name} dest'",
            "uci set firewall.@rule[-1].proto='all'",
            "uci set firewall.@rule[-1].target='REJECT'",
        ]
        if start_time:
            commands.append(f"uci set firewall.@rule[-1].start_time='{start_time}'")
        if end_time:
            commands.append(f"uci set firewall.@rule[-1].stop_time='{end_time}'")
        if weekdays:
            commands.append(f"uci set firewall.@rule[-1].weekdays='{weekdays}'")

    elif family == "ipv6":
        commands += [
            "uci add firewall rule",
            f"uci set firewall.@rule[-1].name='{rule6_name}'",
            "uci set firewall.@rule[-1].src='lan'",
            f"uci set firewall.@rule[-1].src_ip='{src_ip}'",
            "uci set firewall.@rule[-1].dest='wan'",
            "uci set firewall.@rule[-1].family='ipv6'",
            f"uci set firewall.@rule[-1].ipset='{nft6_name} dest'",
            "uci set firewall.@rule[-1].proto='all'",
            "uci set firewall.@rule[-1].target='REJECT'",
        ]
        if start_time:
            commands.append(f"uci set firewall.@rule[-1].start_time='{start_time}'")
        if end_time:
            commands.append(f"uci set firewall.@rule[-1].stop_time='{end_time}'")
        if weekdays:
            commands.append(f"uci set firewall.@rule[-1].weekdays='{weekdays}'")
    else:
        raise ValueError("Unable to determine IP family for resolved device.")

    commands += [
        "uci commit dhcp",
        "uci commit firewall",
        "/etc/init.d/dnsmasq restart",
        "/etc/init.d/firewall restart",
    ]

    return {
        "applied": False,
        "dry_run": True,
        "plan": {
            "mode": "scheduled_domain_block_fw4_dnsmasq",
            "hostname": hostname,
            "src_ip": src_ip,
            "family": family,
            "domains": domains,
            "start_time": start_time,
            "end_time": end_time,
            "weekdays": weekdays,
            "nftset_v4": nft4_name,
            "nftset_v6": nft6_name,
            "dhcp_nftset_section": dhcp_nft_name,
            "commands": commands,
        }
    }