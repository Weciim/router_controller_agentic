def build_dnsmasq_full_install_plan(package_diag: dict) -> dict:
    installed = package_diag.get("installed_packages", [])
    available = package_diag.get("available_packages", [])
    has_full = package_diag.get("checks", {}).get("dnsmasq_full_available", False)

    commands = [
        "apk update",
        "apk info | grep '^dnsmasq' || true",
        "apk search dnsmasq || true",
    ]

    notes = [
        "Inspect package availability before making changes.",
        "Do not remove the active DNS package unless the replacement package is confirmed available.",
        "Re-run dnsmasq capability diagnostics after installation.",
    ]

    if has_full:
        if any(pkg.startswith("dnsmasq-full") for pkg in installed):
            notes.append("dnsmasq-full already appears installed; no package replacement command generated.")
        else:
            commands.extend([
                "# If supported on this feed, install dnsmasq-full first:",
                "apk add dnsmasq-full",
                "# Verify version/build flags after install:",
                "dnsmasq -v 2>&1 || true",
            ])
            notes.append("On current OpenWrt releases using apk, install dnsmasq-full only after confirming it appears in apk search.")
    else:
        notes.append("dnsmasq-full not visible in feeds; inspect repository configuration or release-specific package naming.")

    return {
        "mode": "dnsmasq_package_fix_plan",
        "commands": commands,
        "notes": notes,
        "installed_packages": installed,
        "available_packages_sample": available[:20],
    }