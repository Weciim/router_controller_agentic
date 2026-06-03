def build_qos_install_plan(qos_diag: dict) -> dict:
    checks = qos_diag.get("checks", {})
    preferred = qos_diag.get("preferred_backend")

    commands = ["apk update"]

    if preferred == "qosify":
        if not checks.get("qosify_installed", False):
            commands.append("apk add qosify")
        if not checks.get("tc_present", False) and checks.get("tc_full_available", False):
            commands.append("apk add tc-full")
        if checks.get("cake_module_available", False):
            commands.append("apk add kmod-sched-cake")
    else:
        if not checks.get("sqm_installed", False):
            commands.append("apk add sqm-scripts")
        if not checks.get("luci_app_sqm_installed", False):
            commands.append("apk add luci-app-sqm")
        if not checks.get("tc_present", False) and checks.get("tc_full_available", False):
            commands.append("apk add tc-full")
        if checks.get("cake_module_available", False):
            commands.append("apk add kmod-sched-cake")
        if checks.get("ifb_available", False):
            commands.append("apk add kmod-ifb")

    commands.extend([
        "command -v tc || true",
        "uci show qosify 2>/dev/null || true",
        "uci show sqm 2>/dev/null || true",
    ])

    return {
        "mode": "qos_backend_install",
        "preferred_backend": preferred,
        "commands": commands,
        "notes": [
            "qosify is a strong fit for DSCP/Cake-based application prioritization.",
            "sqm-scripts is the traditional SQM backend on OpenWrt.",
            "Do not enable live QoS apply until tc and a QoS backend are confirmed."
        ],
    }