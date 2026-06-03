from ssh_output_cleaner import strip_openwrt_banner, cleaned_lines


def _text(result: dict) -> str:
    return ((result.get("stdout") or "") + "\n" + (result.get("stderr") or "")).strip()


def diagnose_dnsmasq_packages(ssh_client) -> dict:
    installed_res = ssh_client.run("apk info 2>/dev/null | grep '^dnsmasq' || true", check=False)
    available_res = ssh_client.run("apk search dnsmasq 2>/dev/null || true", check=False)
    version_res = ssh_client.run("dnsmasq -v 2>&1 || true", check=False)

    raw_installed_text = _text(installed_res)
    raw_available_text = _text(available_res)
    raw_version_text = _text(version_res)

    installed_text = strip_openwrt_banner(raw_installed_text)
    available_text = strip_openwrt_banner(raw_available_text)
    version_text = strip_openwrt_banner(raw_version_text)

    installed = cleaned_lines(installed_text)
    available = cleaned_lines(available_text)
    lower_version = version_text.lower()

    has_dnsmasq_full_available = any(pkg.startswith("dnsmasq-full") for pkg in available)
    has_dnsmasq_full_installed = any(pkg.startswith("dnsmasq-full") for pkg in installed)
    nftset_detected = "nftset" in lower_version and "no-nftset" not in lower_version

    recommendations = []
    blockers = []

    if not installed:
        blockers.append("No installed dnsmasq package was detected via apk info.")
    if not nftset_detected:
        blockers.append("Installed dnsmasq does not appear to support nftset.")
    if not has_dnsmasq_full_available:
        recommendations.append("dnsmasq-full was not found in current apk search results; verify feeds and architecture.")
    else:
        recommendations.append("dnsmasq-full is available in the package feeds.")

    if has_dnsmasq_full_available and not has_dnsmasq_full_installed:
        recommendations.append("Prepare a guided replacement from dnsmasq to dnsmasq-full.")
    if has_dnsmasq_full_installed and not nftset_detected:
        recommendations.append("dnsmasq-full is installed but nftset was still not detected; inspect build flags and feeds.")

    return {
        "ok": nftset_detected,
        "installed_packages": installed,
        "available_packages": available,
        "checks": {
            "dnsmasq_full_available": has_dnsmasq_full_available,
            "dnsmasq_full_installed": has_dnsmasq_full_installed,
            "dnsmasq_nftset_detected": nftset_detected,
        },
        "blockers": blockers,
        "recommendations": recommendations,
        "evidence": {
            "dnsmasq_version": version_text[:2000],
            "apk_installed": installed_text[:2000],
            "apk_search": available_text[:4000],
        },
    }