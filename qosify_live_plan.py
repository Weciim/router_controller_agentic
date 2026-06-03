def _slugify(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (value or "").strip().lower())


def _normalize_dns_pattern(pattern: str) -> str:
    pattern = (pattern or "").strip()
    if not pattern:
        return pattern
    if pattern.startswith("dns:"):
        return pattern
    return f"dns:{pattern}"


def _build_mapping_lines(src_ip: str, signature: dict) -> list[str]:
    lines = []
    dscp = signature.get("priority_class", "video")

    for proto in signature.get("protocols", []):
        for port in signature.get("ports", []):
            lines.append(f"{proto}:{port} {dscp}")

    if src_ip:
        lines.append(f"{src_ip} {dscp}")

    for pattern in signature.get("dns_patterns", []):
        norm = _normalize_dns_pattern(pattern)
        if norm:
            lines.append(f"{norm} {dscp}")

    deduped = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)
    return deduped


def _build_heredoc_write_command(remote_path: str, file_body: str) -> str:
    marker = "__QOSIFY_RULE_EOF__"
    return f"cat > {remote_path} <<'{marker}'\n{file_body}{marker}\n"


def build_qosify_live_plan(exec_spec: dict, app_resolution: dict) -> dict:
    target = exec_spec.get("target", {})
    schedule = exec_spec.get("schedule", {})
    policy = exec_spec.get("policy", {})

    if not app_resolution.get("known"):
        return {
            "ok": False,
            "reason": "Unknown application signature; refusing live apply.",
            "plan": None,
        }

    hostname = target.get("hostname") or "unknown-host"
    src_ip = target.get("ip")
    signature = app_resolution.get("signature", {})
    app_name = app_resolution.get("canonical_name")

    mapping_lines = _build_mapping_lines(src_ip, signature)
    file_name = f"90-llm-{_slugify(hostname)}-{_slugify(app_name)}.conf"
    remote_path = f"/etc/qosify/{file_name}"

    file_body = "\n".join([
        "# Managed by router agent",
        f"# Host: {hostname}",
        f"# App: {app_name}",
        f"# IP: {src_ip or 'unknown'}",
        f"# Days: {','.join(schedule.get('days') or []) or 'unspecified'}",
        f"# Start: {schedule.get('start_time') or 'unspecified'}",
        f"# End: {schedule.get('end_time') or 'unspecified'}",
        *mapping_lines,
        ""
    ])

    commands = [
        "uci set qosify.wan.disabled='0'",
        "uci set qosify.wan.ingress='1'",
        "uci set qosify.wan.egress='1'",
        "uci set qosify.wan.mode='diffserv4'",
        "uci set qosify.wan.nat='1'",
        "uci set qosify.wan.host_isolate='1'",
        "uci commit qosify",
        _build_heredoc_write_command(remote_path, file_body),
        "/etc/init.d/qosify enable || true",
        "/etc/init.d/qosify restart",
        f"test -s {remote_path}",
        f"sed -n '1,120p' {remote_path}",
        "uci show qosify",
        "qosify-status 2>/dev/null || true",
        "tc -s qdisc 2>/dev/null || true",
    ]

    return {
        "ok": True,
        "reason": None,
        "plan": {
            "mode": "qosify_live_apply",
            "hostname": hostname,
            "src_ip": src_ip,
            "application": app_name,
            "application_signature": signature,
            "remote_path": remote_path,
            "file_body": file_body,
            "expected_lines": mapping_lines,
            "commands": commands,
            "schedule": schedule,
            "policy": policy,
        },
    }