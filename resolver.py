from difflib import get_close_matches


def _norm(value):
    return (value or "").strip().lower()


def _device_label(device: dict) -> str:
    return (
        device.get("hostname")
        or device.get("ip")
        or device.get("macaddr")
        or device.get("duid")
        or "unknown-device"
    )


def resolve_target_device(validated: dict, devices: list[dict]) -> dict:
    target = _norm(validated.get("target_device"))

    if not target:
        return {
            "ok": False,
            "device": None,
            "reason": "No target_device was provided.",
            "available_devices": [_device_label(d) for d in devices],
            "candidates": [],
        }

    exact_matches = []
    hostname_candidates = []

    for d in devices:
        hostname = _norm(d.get("hostname"))
        ip = _norm(d.get("ip"))
        macaddr = _norm(d.get("macaddr"))
        duid = _norm(d.get("duid"))

        if target in {hostname, ip, macaddr, duid}:
            exact_matches.append(d)
        elif hostname:
            hostname_candidates.append((hostname, d))

    if exact_matches:
        best = exact_matches[0]
        return {
            "ok": True,
            "device": best,
            "reason": None,
            "available_devices": [_device_label(d) for d in devices],
            "candidates": exact_matches,
        }

    names = [name for name, _ in hostname_candidates]
    close = get_close_matches(target, names, n=5, cutoff=0.5)

    close_candidates = [d for name, d in hostname_candidates if name in close]

    return {
        "ok": False,
        "device": None,
        "reason": f"Device '{validated.get('target_device')}' was not found on the router.",
        "available_devices": [_device_label(d) for d in devices],
        "candidates": close_candidates,
    }


def build_clarification_response(validated: dict, resolution: dict) -> dict:
    available_devices = resolution.get("available_devices") or []
    available_text = ", ".join(available_devices) if available_devices else "no currently discovered devices"

    return {
        "intent": "clarify_request",
        "action": "ask_clarification",
        "target_device": validated.get("target_device"),
        "target_profile": validated.get("target_profile"),
        "service": validated.get("service"),
        "domains": validated.get("domains"),
        "category": validated.get("category"),
        "days": validated.get("days"),
        "start_time": validated.get("start_time"),
        "end_time": validated.get("end_time"),
        "duration_minutes": validated.get("duration_minutes"),
        "priority": validated.get("priority"),
        "bandwidth_mbps": validated.get("bandwidth_mbps"),
        "requires_confirmation": True,
        "needs_clarification": True,
        "clarification_question": (
            f"Device '{validated.get('target_device')}' was not found on the router. "
            f"Available devices: {available_text}. Which one should I use?"
        ),
        "status": "needs_clarification",
    }


def enrich_plan_with_device(plan: dict, matched_device: dict) -> dict:
    enriched = dict(plan)
    enriched["resolved_device"] = {
        "hostname": matched_device.get("hostname"),
        "interface": matched_device.get("interface"),
        "ip": matched_device.get("ip"),
        "duid": matched_device.get("duid"),
        "iaid": matched_device.get("iaid"),
        "macaddr": matched_device.get("macaddr"),
        "source": matched_device.get("source"),
    }
    return enriched