from ssh_output_cleaner import strip_openwrt_banner, cleaned_lines


def _clean(result: dict) -> str:
    text = ((result.get("stdout") or "") + "\n" + (result.get("stderr") or "")).strip()
    return strip_openwrt_banner(text)


def diagnose_qos_packages(ssh_client) -> dict:
    installed_res = ssh_client.run(
        "apk info 2>/dev/null | grep -E '^(qosify|sqm-scripts|luci-app-sqm|tc-full|ip-full|kmod-sched-cake|kmod-ifb)$' || true",
        check=False,
    )
    search_res = ssh_client.run(
        "apk search qosify 2>/dev/null || true; "
        "apk search sqm 2>/dev/null || true; "
        "apk search tc-full 2>/dev/null || true; "
        "apk search kmod-sched-cake 2>/dev/null || true; "
        "apk search kmod-ifb 2>/dev/null || true",
        check=False,
    )
    tc_res = ssh_client.run("command -v tc >/dev/null 2>&1 && echo yes || echo no", check=False)
    cake_mod_res = ssh_client.run("lsmod | grep -E 'sch_cake|ifb' || true", check=False)
    qosify_cfg_res = ssh_client.run("uci show qosify 2>/dev/null || true", check=False)
    sqm_cfg_res = ssh_client.run("uci show sqm 2>/dev/null || true", check=False)

    installed = cleaned_lines(_clean(installed_res))
    available = cleaned_lines(_clean(search_res))
    tc_present = "yes" in _clean(tc_res).lower()
    cake_loaded = bool(cleaned_lines(_clean(cake_mod_res)))
    qosify_cfg = _clean(qosify_cfg_res)
    sqm_cfg = _clean(sqm_cfg_res)

    checks = {
        "tc_present": tc_present,
        "qosify_installed": "qosify" in installed,
        "sqm_installed": "sqm-scripts" in installed,
        "luci_app_sqm_installed": "luci-app-sqm" in installed,
        "tc_full_installed": "tc-full" in installed,
        "cake_module_loaded": cake_loaded,
        "qosify_available": any("qosify" in x for x in available),
        "sqm_available": any("sqm" in x for x in available),
        "tc_full_available": any("tc-full" in x for x in available),
        "cake_module_available": any("kmod-sched-cake" in x for x in available),
        "ifb_available": any("kmod-ifb" in x for x in available),
        "qosify_config_present": bool(qosify_cfg),
        "sqm_config_present": bool(sqm_cfg),
    }

    blockers = []
    if not checks["tc_present"]:
        blockers.append("tc is not installed or not in PATH.")
    if not (checks["qosify_installed"] or checks["sqm_installed"]):
        blockers.append("No QoS backend package is installed.")

    recommendations = []
    if checks["qosify_available"] and not checks["qosify_installed"]:
        recommendations.append("Install qosify for DSCP/Cake-based app prioritization.")
    if checks["sqm_available"] and not checks["sqm_installed"]:
        recommendations.append("Install sqm-scripts for classic SQM shaping.")
    if checks["tc_full_available"] and not checks["tc_present"]:
        recommendations.append("Install tc-full because live QoS apply depends on tc.")
    if checks["cake_module_available"] and not checks["cake_module_loaded"]:
        recommendations.append("Install/load kmod-sched-cake for Cake-based queue management.")

    preferred_backend = None
    if checks["qosify_available"]:
        preferred_backend = "qosify"
    elif checks["sqm_available"]:
        preferred_backend = "sqm"

    return {
        "ok": True,
        "installed_packages": installed,
        "available_packages": available,
        "checks": checks,
        "blockers": blockers,
        "recommendations": recommendations,
        "preferred_backend": preferred_backend,
        "evidence": {
            "qosify_config_excerpt": qosify_cfg[:4000],
            "sqm_config_excerpt": sqm_cfg[:4000],
        },
    }