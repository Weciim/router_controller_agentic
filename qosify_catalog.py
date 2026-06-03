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
        "priority_class": "video",
        "default_priority": "high",
        "description": "Approximate Google Meet signature for prioritization."
    }
}


import re
from application_registry import APPLICATION_SIGNATURES

def _normalize_app_name(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("&", "and")
    value = re.sub(r"[\s\-_./]+", "", value)
    value = re.sub(r"[^a-z0-9]", "", value)
    return value
def _normalize_app_name(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("&", "and")
    value = re.sub(r"[\s\-_./]+", "", value)
    value = re.sub(r"[^a-z0-9]", "", value)
    return value


def resolve_application_signature(app_name: str) -> dict:
    requested = app_name or ""
    normalized_requested = _normalize_app_name(requested)

    for canonical_name, signature in APPLICATION_SIGNATURES.items():
        alias_values = [canonical_name] + list(signature.get("aliases", []))
        normalized_aliases = {_normalize_app_name(v) for v in alias_values}

        if normalized_requested in normalized_aliases:
            return {
                "known": True,
                "canonical_name": canonical_name,
                "signature": signature,
                "reason": None,
            }

    return {
        "known": False,
        "canonical_name": normalized_requested or None,
        "signature": {
            "aliases": [requested] if requested else [],
            "protocols": ["tcp", "udp"],
            "ports": [80, 443],
            "dns_patterns": [],
            "priority_class": "besteffort",
            "default_priority": "medium",
            "description": "Fallback generic app signature."
        },
        "reason": f"Unknown application: {requested}",
    }