from ssh_output_cleaner import strip_openwrt_banner


def execute_qos_install_plan(ssh_client, plan: dict, dry_run: bool = True) -> dict:
    commands = plan.get("commands", [])
    results = []

    for cmd in commands:
        if dry_run:
            results.append({
                "command": cmd,
                "ran": False,
                "dry_run": True,
                "stdout": "",
                "stderr": "",
                "exit_code": None,
            })
            continue

        res = ssh_client.run(cmd, check=False)
        results.append({
            "command": cmd,
            "ran": True,
            "dry_run": False,
            "stdout": strip_openwrt_banner(res.get("stdout", "")),
            "stderr": strip_openwrt_banner(res.get("stderr", "")),
            "exit_code": res.get("exit_code"),
        })

    ok = all((r["dry_run"] or r["exit_code"] == 0 or r["exit_code"] is None) for r in results)

    return {
        "ok": ok,
        "mode": "qos_backend_install",
        "dry_run": dry_run,
        "results": results,
    }