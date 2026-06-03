from ssh_output_cleaner import strip_openwrt_banner, cleaned_lines


def _stdout(result: dict) -> str:
    return strip_openwrt_banner((result.get("stdout") or "").strip())


def probe_qos_capabilities(client) -> dict:
    sqm_installed = client.run(
        "apk info 2>/dev/null | grep -E '^(sqm-scripts|luci-app-sqm|qosify)$' || true",
        check=False,
        prefer_ssh=True,
    )
    sqm_cfg = client.run("uci show sqm 2>/dev/null || true", check=False, prefer_ssh=True)
    qosify_cfg = client.run("uci show qosify 2>/dev/null || true", check=False, prefer_ssh=True)
    tc_exists = client.run("command -v tc >/dev/null 2>&1 && echo yes || echo no", check=False, prefer_ssh=True)
    nft_exists = client.run("command -v nft >/dev/null 2>&1 && echo yes || echo no", check=False, prefer_ssh=True)
    wan_if = client.run(
        "uci -q get network.wan.device 2>/dev/null || uci -q get network.wan.ifname 2>/dev/null || true",
        check=False,
        prefer_ssh=True,
    )

    sqm_installed_text = _stdout(sqm_installed)
    sqm_cfg_text = _stdout(sqm_cfg)
    qosify_cfg_text = _stdout(qosify_cfg)
    tc_text = _stdout(tc_exists).lower()
    nft_text = _stdout(nft_exists).lower()
    wan_device = _stdout(wan_if).splitlines()[-1].strip() if _stdout(wan_if).strip() else ""

    installed_lines = cleaned_lines(sqm_installed_text)
    tc_present = "yes" in tc_text
    nft_present = "yes" in nft_text
    sqm_config_present = bool(sqm_cfg_text)
    qosify_config_present = bool(qosify_cfg_text)
    qos_pkg_installed = any(x in {"sqm-scripts", "luci-app-sqm", "qosify"} for x in installed_lines)

    checks = {
        "tc_present": tc_present,
        "nft_present": nft_present,
        "sqm_package_installed": qos_pkg_installed,
        "sqm_config_present": sqm_config_present or qosify_config_present,
        "wan_device_detected": bool(wan_device),
        "qos_priority_dry_run_ready": bool(wan_device),
        "qos_priority_live_ready": tc_present and qos_pkg_installed and bool(wan_device),
    }

    blockers = []
    if not tc_present:
        blockers.append("tc command not available.")
    if not wan_device:
        blockers.append("WAN device could not be detected.")
    if not qos_pkg_installed:
        blockers.append("sqm-scripts/luci-app-sqm/qosify is not installed.")

    recommendations = []
    if not qos_pkg_installed:
        recommendations.append("Install sqm-scripts, luci-app-sqm, or qosify before live QoS apply.")
    if checks["qos_priority_dry_run_ready"]:
        recommendations.append("Router can generate QoS priority plans in dry-run mode.")

    return {
        "ok": True,
        "checks": checks,
        "blockers": blockers,
        "recommendations": recommendations,
        "evidence": {
            "installed_qos_packages": installed_lines,
            "sqm_config_excerpt": sqm_cfg_text[:4000],
            "qosify_config_excerpt": qosify_cfg_text[:4000],
            "wan_device": wan_device,
        },
    }