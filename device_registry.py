def parse_odhcpd_leases(text: str):
    devices = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") and len(line.split()) < 9:
            continue

        parts = line.split()
        if len(parts) < 9:
            continue

        iface = parts[1] if parts[0] == "#" else parts[0]
        duid = parts[2] if parts[0] == "#" else parts[1]
        iaid = parts[3] if parts[0] == "#" else parts[2]
        hostname = parts[4] if parts[0] == "#" else parts[3]
        expiry = parts[5] if parts[0] == "#" else parts[4]
        hostid = parts[6] if parts[0] == "#" else parts[5]
        prefix_len = parts[7] if parts[0] == "#" else parts[6]
        ip = parts[8] if parts[0] == "#" else parts[7]

        devices.append({
            "interface": iface,
            "duid": duid,
            "iaid": iaid,
            "hostname": hostname,
            "expiry": expiry,
            "host_id": hostid,
            "prefix_len": prefix_len,
            "ip": ip,
        })

    return devices


def match_device(name: str, devices: list[dict]):
    if not name:
        return None

    name_norm = name.strip().lower()

    exact = [d for d in devices if d.get("hostname", "").lower() == name_norm]
    if exact:
        return exact[0]

    partial = [d for d in devices if name_norm in d.get("hostname", "").lower()]
    if partial:
        return partial[0]

    return None