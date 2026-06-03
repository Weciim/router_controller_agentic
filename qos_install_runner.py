from ssh_output_cleaner import strip_openwrt_banner


def run_qos_install_plan(ssh_client, plan: dict, execute: bool = False) -> dict:
    commands = plan.get("commands", [])
    results = []

    for cmd in commands:
        if not execute:
            results.append({
                "command": cmd,
                "executed": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
            })
            continue

        res = ssh_client.run(cmd, check=False)
        results.append({
            "command": cmd,
            "executed": True,
            "exit_code": res.get("exit_code"),
            "stdout": strip_openwrt_banner(res.get("stdout", ""))[:4000],
            "stderr": strip_openwrt_banner(res.get("stderr", ""))[:4000],
        })

    failed = [
        r for r in results
        if r["executed"] and r["exit_code"] not in (0, None)
    ]

    return {
        "ok": len(failed) == 0,
        "executed": execute,
        "mode": "qos_backend_install",
        "results": results,
        "failed_commands": failed,
    }