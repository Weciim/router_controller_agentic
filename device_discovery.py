
import re


def _strip_prefix(ip: str | None) -> str | None:
    if not ip:
        return ip
    return ip.split("/")[0]


def _norm_hostname(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _norm_ip(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    return _strip_prefix(value)


def _device_key(hostname, ip):
    return ((hostname or "").lower(), ip or "")


def _add_device(devices, seen, hostname=None, ip=None, interface=None, source=None, duid=None, iaid=None, macaddr=None):
    hostname = _norm_hostname(hostname)
    ip = _norm_ip(ip)

    if not hostname and not ip:
        return

    key = _device_key(hostname, ip)
    if key in seen:
        return

    seen.add(key)
    devices.append({
        "hostname": hostname,
        "ip": ip,
        "interface": interface,
        "duid": duid,
        "iaid": iaid,
        "macaddr": macaddr,
        "source": source,
    })


def parse_odhcpd_leases_text(text: str) -> list[dict]:
    devices = []
    seen = set()

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()

        if len(parts) >= 9 and parts[0] == "#":
            _add_device(
                devices, seen,
                hostname=parts[4],
                ip=parts[8],
                interface=parts[1],
                duid=parts[2],
                iaid=parts[3],
                source="odhcpd.leases",
            )
        elif len(parts) >= 4:
            _add_device(
                devices, seen,
                hostname=parts[3],
                ip=parts[2],
                source="dhcp.leases",
            )

    return devices


def parse_hosts_text(text: str, source_name: str) -> list[dict]:
    devices = []
    seen = set()

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = re.split(r"\s+", line)
        if len(parts) >= 2:
            ip = parts[0]
            hostname = parts[1]
            _add_device(devices, seen, hostname=hostname, ip=ip, source=source_name)

    return devices


def parse_luci_dhcp_leases(payload) -> list[dict]:
    devices = []
    seen = set()

    if not isinstance(payload, dict):
        return devices

    for entry in payload.get("dhcp_leases", []) or []:
        if not isinstance(entry, dict):
            continue
        _add_device(
            devices, seen,
            hostname=entry.get("hostname"),
            ip=entry.get("ipaddr"),
            macaddr=entry.get("macaddr"),
            duid=entry.get("duid"),
            source="luci-rpc.dhcp_leases",
        )

    for entry in payload.get("dhcp6_leases", []) or []:
        if not isinstance(entry, dict):
            continue

        ip6addrs = entry.get("ip6addrs") or []
        if isinstance(ip6addrs, list) and ip6addrs:
            for ip in ip6addrs:
                _add_device(
                    devices, seen,
                    hostname=entry.get("hostname"),
                    ip=ip,
                    macaddr=entry.get("macaddr"),
                    duid=entry.get("duid"),
                    source="luci-rpc.dhcp6_leases",
                )
        else:
            _add_device(
                devices, seen,
                hostname=entry.get("hostname"),
                ip=entry.get("ip6addr"),
                macaddr=entry.get("macaddr"),
                duid=entry.get("duid"),
                source="luci-rpc.dhcp6_leases",
            )

    return devices


def parse_ubus_lease_payload(payload, source_name: str) -> list[dict]:
    devices = []
    seen = set()

    if not isinstance(payload, dict):
        return devices

    for iface, iface_payload in payload.items():
        if isinstance(iface_payload, dict) and "leases" in iface_payload:
            entries = iface_payload.get("leases") or []
        elif isinstance(iface_payload, list):
            entries = iface_payload
        else:
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            hostname = (
                entry.get("hostname")
                or entry.get("name")
                or entry.get("host")
                or entry.get("client-hostname")
            )

            candidate_ips = []

            for key in ["ip", "address", "ipv4", "ipv6", "ipaddr", "ip6addr"]:
                value = entry.get(key)
                if value:
                    candidate_ips.append(value)

            ip6addrs = entry.get("ip6addrs")
            if isinstance(ip6addrs, list):
                candidate_ips.extend(ip6addrs)

            if not candidate_ips:
                candidate_ips = [None]

            for ip in candidate_ips:
                _add_device(
                    devices, seen,
                    hostname=hostname,
                    ip=ip,
                    interface=iface,
                    duid=entry.get("duid"),
                    iaid=entry.get("iaid"),
                    macaddr=entry.get("macaddr"),
                    source=source_name,
                )

    return devices


def discover_devices(client) -> list[dict]:
    devices = []
    seen = set()

    all_found = []

    try:
        all_found.extend(parse_luci_dhcp_leases(client.get_luci_dhcp_leases()))
    except Exception:
        pass

    try:
        all_found.extend(parse_ubus_lease_payload(client.get_dhcp_ipv4_leases(), "ubus.ipv4leases"))
    except Exception:
        pass

    try:
        all_found.extend(parse_ubus_lease_payload(client.get_dhcp_ipv6_leases(), "ubus.ipv6leases"))
    except Exception:
        pass

    try:
        all_found.extend(parse_odhcpd_leases_text(client.get_odhcpd_leases()))
    except Exception:
        pass

    try:
        all_found.extend(parse_hosts_text(client.get_odhcpd_hosts(), "odhcpd.hosts"))
    except Exception:
        pass

    try:
        all_found.extend(parse_hosts_text(client.get_dns_hosts(), "dns.hosts"))
    except Exception:
        pass

    for item in all_found:
        _add_device(
            devices, seen,
            hostname=item.get("hostname"),
            ip=item.get("ip"),
            interface=item.get("interface"),
            duid=item.get("duid"),
            iaid=item.get("iaid"),
            macaddr=item.get("macaddr"),
            source=item.get("source"),
        )

    return devices