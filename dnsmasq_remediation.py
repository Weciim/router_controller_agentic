from datetime import datetime


def build_dnsmasq_remediation_plan(package_diag: dict) -> dict:
    checks = package_diag.get("checks", {})
    installed = package_diag.get("installed_packages", [])
    available = package_diag.get("available_packages", [])

    has_full_available = checks.get("dnsmasq_full_available", False)
    has_full_installed = checks.get("dnsmasq_full_installed", False)

    commands = [
        "apk update",
        "apk info | grep '^dnsmasq' || true",
        "apk search dnsmasq || true",
    ]

    notes = [
        "Apply only if dnsmasq-full is visible in the package feeds.",
        "Re-run dnsmasq diagnostics after package changes.",
        "Do not allow real domain blocking until nftset is confirmed in dnsmasq compile options.",
    ]

    if has_full_installed:
        notes.append("dnsmasq-full already appears installed; only verification commands are needed.")
    elif has_full_available:
        commands.extend([
            "apk add dnsmasq-full",
            "dnsmasq -v 2>&1 || true",
        ])
        notes.append("If package conflicts occur, inspect installed dnsmasq variants before removal.")
    else:
        notes.append("dnsmasq-full was not found in current feeds, so no install command was generated.")

    return {
        "mode": "dnsmasq_remediation",
        "commands": commands,
        "notes": notes,
        "installed_packages": installed,
        "available_packages_sample": available[:20],
    }


def execute_dnsmasq_remediation_plan(ssh_client, plan: dict, dry_run: bool = True) -> dict:
    commands = plan.get("commands", [])

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "applied_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "commands": commands,
            "notes": plan.get("notes", []),
        }

    results = []
    for cmd in commands:
        if not cmd.strip() or cmd.strip().startswith("#"):
            continue
        res = ssh_client.run(cmd, check=False)
        results.append(res)

    return {
        "applied": True,
        "dry_run": False,
        "applied_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "results": results,
        "notes": plan.get("notes", []),
    }