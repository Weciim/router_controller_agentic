import json
from device_cache import load_device_cache
from device_discovery import discover_devices


def _norm(v):
    return (v or "").strip()


def _key(dev):
    return (
        _norm(dev.get("hostname")).lower(),
        _norm(dev.get("ip")),
        _norm(dev.get("macaddr")).lower(),
        _norm(dev.get("duid")).lower(),
    )


def merge_devices(*device_lists):
    merged = {}
    for lst in device_lists:
        for dev in lst or []:
            k = _key(dev)
            if k == ("", "", "", ""):
                continue
            if k not in merged:
                merged[k] = dict(dev)
            else:
                for kk, vv in dev.items():
                    if vv not in [None, "", []]:
                        merged[k][kk] = vv
    return list(merged.values())


def host_hints_to_devices(payload):
    results = []
    if not isinstance(payload, dict):
        return results

    for _, item in payload.items():
        if not isinstance(item, dict):
            continue

        hostname = item.get("name") or item.get("hostname")
        ipaddrs = item.get("ipaddrs") or []
        macaddr = item.get("macaddr")

        if ipaddrs:
            for ip in ipaddrs:
                results.append({
                    "hostname": hostname,
                    "ip": ip.split("/")[0],
                    "macaddr": macaddr,
                    "duid": None,
                    "iaid": None,
                    "interface": None,
                    "source": "luci-rpc.host_hints",
                })
        else:
            results.append({
                "hostname": hostname,
                "ip": None,
                "macaddr": macaddr,
                "duid": None,
                "iaid": None,
                "interface": None,
                "source": "luci-rpc.host_hints",
            })

    return results


def get_all_available_devices(client):
    live_devices = discover_devices(client)
    cached_devices = load_device_cache()

    try:
        host_hints = client.get_host_hints()
    except Exception:
        host_hints = None

    hint_devices = host_hints_to_devices(host_hints)

    return merge_devices(live_devices, cached_devices, hint_devices)