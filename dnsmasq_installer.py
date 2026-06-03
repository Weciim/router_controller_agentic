from ssh_output_cleaner import strip_openwrt_banner


def _clean(text: str) -> str:
    return strip_openwrt_banner(text or "").strip()


def build_dnsmasq_full_upgrade_plan(package_diag: dict, feed_diag: dict) -> dict:
    pkg_checks = (package_diag or {}).get("checks", {})
    feed_checks = (feed_diag or {}).get("checks", {})

    full_available = bool(pkg_checks.get("dnsmasq_full_available")) or bool(feed_checks.get("dnsmasq_full_search_has_hits"))
    full_installed = bool(pkg_checks.get("dnsmasq_full_installed"))

    commands = [
        "apk update",
        "apk search dnsmasq || true",
        "apk info | grep '^dnsmasq' || true",
        "apk policy dnsmasq 2>&1 || true",
    ]

    notes = [
        "Do not remove the active DNS package before the replacement package is locally available.",
        "After package change, verify compile flags with dnsmasq -v.",
        "Only unblock real apply when nftset is visible in dnsmasq compile options.",
    ]

    if full_installed:
        commands.extend([
            "dnsmasq -v 2>&1 || true",
            "/etc/init.d/dnsmasq restart || true",
        ])
        notes.append("dnsmasq-full already appears installed; only verification is required.")
    elif full_available:
        commands.extend([
            "apk add --download-only dnsmasq-full",
            "apk del dnsmasq",
            "apk add dnsmasq-full",
            "dnsmasq -v 2>&1 || true",
            "/etc/init.d/dnsmasq restart || true",
        ])
        notes.append("A download-first strategy reduces the risk of losing package resolution mid-upgrade.")
    else:
        notes.append("dnsmasq-full is not available in current feeds, so no install path can be generated.")

    return {
        "mode": "dnsmasq_full_upgrade",
        "full_available": full_available,
        "full_installed": full_installed,
        "commands": commands,
        "notes": notes,
    }


def execute_dnsmasq_full_upgrade_plan(ssh_client, plan: dict, dry_run: bool = True) -> dict:
    commands = plan.get("commands", [])

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "commands": commands,
            "notes": plan.get("notes", []),
        }

    results = []
    all_ok = True

    for cmd in commands:
        if not cmd.strip() or cmd.strip().startswith("#"):
            continue

        res = ssh_client.run(cmd, check=False)
        ok = bool(res.get("ok"))
        all_ok = all_ok and ok

        results.append({
            "command": cmd,
            "ok": ok,
            "exit_status": res.get("exit_status"),
            "stdout": _clean(res.get("stdout", ""))[:3000],
            "stderr": _clean(res.get("stderr", ""))[:3000],
        })

    return {
        "applied": all_ok,
        "dry_run": False,
        "results": results,
        "notes": plan.get("notes", []),
    }