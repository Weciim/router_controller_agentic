def parse_dnsmasq_capabilities(text: str) -> dict:
    raw = text or ""
    lower = raw.lower()

    return {
        "supports_nftset": "nftset" in lower and "no-nftset" not in lower,
        "supports_ipset": "ipset" in lower and "no-ipset" not in lower,
        "raw": raw,
    }


def dnsmasq_capability_summary(text: str) -> dict:
    parsed = parse_dnsmasq_capabilities(text)

    return {
        "supports_nftset": parsed["supports_nftset"],
        "supports_ipset": parsed["supports_ipset"],
        "ready_for_real_domain_apply": parsed["supports_nftset"],
        "raw_excerpt": parsed["raw"][:1000],
    }