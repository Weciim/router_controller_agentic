from difflib import get_close_matches

APP_CATALOG = {
    "google_meet": {
        "aliases": ["google meet", "meet", "gmeet", "google me", "google mee"],
        "protocols": ["udp", "tcp"],
        "ports": [443, 3478, 3479, 19302, 19305],
        "dns_patterns": [
            "dns:*.meet.google.com",
            "dns:*.googleapis.com",
            "dns:*.gstatic.com",
        ],
        "priority_class": "AF41",
        "default_priority": "high",
        "description": "Approximate Google Meet signature for prioritization."
    }
}


def resolve_application_signature(name: str) -> dict:
    raw = (name or "").strip().lower()
    if not raw:
        return {
            "known": False,
            "canonical_name": None,
            "signature": None,
            "reason": "No application name provided."
        }

    alias_map = {}
    for key, meta in APP_CATALOG.items():
        alias_map[key] = key
        for alias in meta.get("aliases", []):
            alias_map[alias.lower()] = key

    if raw in alias_map:
        key = alias_map[raw]
        return {
            "known": True,
            "canonical_name": key,
            "signature": APP_CATALOG[key],
            "reason": None
        }

    match = get_close_matches(raw, list(alias_map.keys()), n=1, cutoff=0.8)
    if match:
        key = alias_map[match[0]]
        return {
            "known": True,
            "canonical_name": key,
            "signature": APP_CATALOG[key],
            "reason": f"Resolved fuzzy match from '{raw}' to '{match[0]}'."
        }

    return {
        "known": False,
        "canonical_name": raw,
        "signature": {
            "name": raw,
            "aliases": [raw],
            "protocols": [],
            "ports": [],
            "dns_patterns": [],
            "priority_class": "CS0",
            "default_priority": "normal",
            "description": "Unknown application; needs clarification or manual profile."
        },
        "reason": "Unknown application signature."
    }